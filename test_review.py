"""
Test script for AI Code Reviewer.

Sends a deliberately buggy "PR diff" to the /review endpoint so you can
verify that all 6 agents + manager + auto-fix produce meaningful output.

PLANTED ISSUES (what the agents should catch):
──────────────────────────────────────────────
Correctness:        off-by-one pagination, missing null check, implicit None return,
                    unchecked negative amount, bare except swallowing errors
Security:           6x SQL injection, 2x hardcoded secrets, eval() with user input,
                    MD5 for passwords, XSS, no input validation on UPDATE
Performance:        N+1 query, O(n²) duplicate check, full table load instead of LIMIT,
                    string concat in loop, unbounded cache, sync batch API calls
Concurrency:        race condition in transfer_balance (read-modify-write without txn),
                    global shared DB connection with no thread safety
Maintainability:    variables named d/x/tmp, process_data does 5 things, 90-line class,
                    duplicated tax logic, no docstrings on critical functions
Backward compat:    get_user() signature changed (added new required-looking params),
                    original simple function replaced with class method
Observability:      print("error") with no context, delete_user silently swallows errors,
                    no logging anywhere, no request IDs
Dependencies:       unpinned flask/requests, old jinja2 with known CVEs,
                    old urllib3 with known CVEs
Test coverage:      literally zero tests for any of this code
──────────────────────────────────────────────

Usage:
    Terminal 1:  cd ai-code-reviewer && uvicorn main:app --reload --port 8000
    Terminal 2:  python test_review.py
"""

import requests
import json
import sys
import time

SERVER = "http://localhost:8000"

# ── The "bad PR" diff ──
# Three files: a user service with tons of bugs, a payment handler
# with more bugs, and a requirements.txt with vulnerable deps.

TEST_DIFF = [
    {
        "filename": "app/user_service.py",
        "status": "modified",
        "additions": 92,
        "deletions": 5,
        "patch": "\n".join([
            "@@ -1,8 +1,92 @@",
            "-from app.models import User",
            "-",
            "-def get_user(user_id):",
            '-    """Fetch a user by ID."""',
            "-    return User.query.get(user_id)",
            "+import sqlite3",
            "+import hashlib",
            "+",
            '+DB_PASSWORD = \"admin123!@#\"',
            '+DATABASE_URL = f\"sqlite:///users.db\"',
            "+",
            "+connection = sqlite3.connect(DATABASE_URL)",
            "+",
            "+",
            "+class UserService:",
            "+    def get_user(self, user_id, include_orders=False, include_profile=True):",
            "+        # signature changed from get_user(user_id) — breaks all callers",
            '+        query = f\"SELECT * FROM users WHERE id = \'{user_id}\'\"',
            "+        cursor = connection.execute(query)",
            "+        user = cursor.fetchone()",
            "+",
            "+        if include_orders:",
            "+            order_ids = connection.execute(",
            '+                f\"SELECT id FROM orders WHERE user_id = \'{user_id}\'\"',
            "+            ).fetchall()",
            "+            for oid in order_ids:",
            "+                order = connection.execute(",
            '+                    f\"SELECT * FROM orders WHERE id = \'{oid[0]}\'\"',
            "+                ).fetchone()",
            "+                user['orders'] = user.get('orders', []) + [order]",
            "+",
            "+        return user",
            "+",
            "+    def list_users(self, page, limit):",
            "+        # BUG: page 1 skips the first 'limit' rows (off-by-one)",
            "+        offset = page * limit  # should be (page - 1) * limit",
            '+        all_users = connection.execute(\"SELECT * FROM users\").fetchall()',
            "+        return all_users[offset:offset + limit]",
            "+",
            "+    def find_duplicates(self, users):",
            "+        duplicates = []",
            "+        for i in range(len(users)):",
            "+            for j in range(len(users)):",
            "+                if i != j and users[i]['email'] == users[j]['email']:",
            "+                    duplicates.append(users[i])",
            "+        return duplicates",
            "+",
            "+    def transfer_balance(self, from_id, to_id, amount):",
            "+        from_balance = connection.execute(",
            '+            f\"SELECT balance FROM users WHERE id = \'{from_id}\'\"',
            "+        ).fetchone()[0]",
            "+        to_balance = connection.execute(",
            '+            f\"SELECT balance FROM users WHERE id = \'{to_id}\'\"',
            "+        ).fetchone()[0]",
            "+        connection.execute(",
            '+            f\"UPDATE users SET balance = {from_balance - amount} WHERE id = \'{from_id}\'\"',
            "+        )",
            "+        connection.execute(",
            '+            f\"UPDATE users SET balance = {to_balance + amount} WHERE id = \'{to_id}\'\"',
            "+        )",
            "+        connection.commit()",
            "+",
            "+    def delete_user(self, user_id):",
            "+        try:",
            '+            connection.execute(f\"DELETE FROM users WHERE id = \'{user_id}\'\")',
            "+            connection.commit()",
            "+        except:",
            "+            pass",
            "+",
            "+    def process_data(self, d):",
            "+        x = d.get('val')",
            "+        tmp = []",
            "+        for i in d.get('items'):",
            "+            if i > 0:",
            "+                tmp.append(i * 2)",
            "+        result = eval(d.get('formula', '0'))",
            "+        return {'x': x, 'tmp': tmp, 'r': result}",
            "+",
            "+    def hash_password(self, password):",
            "+        return hashlib.md5(password.encode()).hexdigest()",
            "+",
            "+    def search_users(self, query):",
            '+        return f\"<h1>Search results for: {query}</h1>\"',
            "+",
            "+    def export_users(self):",
            '+        users = connection.execute(\"SELECT * FROM users\").fetchall()',
            "+        data = []",
            "+        for u in users:",
            '+            result = \"\"',
            "+            for field in u:",
            '+                result = result + str(field) + \",\"',
            "+            data.append(result)",
            '+        return \"\\n\".join(data)',
            "+",
            "+    def update_user(self, user_id, data):",
            "+        for key, value in data.items():",
            "+            connection.execute(",
            '+                f\"UPDATE users SET {key} = \'{value}\' WHERE id = \'{user_id}\'\"',
            "+            )",
            "+        connection.commit()",
        ]),
    },
    {
        "filename": "app/payment_handler.py",
        "status": "added",
        "additions": 52,
        "deletions": 0,
        "patch": "\n".join([
            "@@ -0,0 +1,52 @@",
            "+import requests",
            "+import json",
            "+",
            '+API_KEY = \"sk-live-a1b2c3d4e5f6g7h8i9j0klmnopqrstuvwxyz\"',
            "+",
            "+cache = {}",
            "+",
            "+",
            "+def process_payment(user_id, amount, currency):",
            "+    response = requests.post(",
            '+        \"https://api.payments.com/charge\",',
            '+        headers={\"Authorization\": f\"Bearer {API_KEY}\"},',
            '+        json={\"user\": user_id, \"amount\": amount, \"currency\": currency}',
            "+    )",
            '+    cache[f\"{user_id}_{amount}\"] = response.json()',
            "+    return response.json()",
            "+",
            "+",
            "+def refund_payment(payment_id):",
            "+    try:",
            '+        response = requests.post(f\"https://api.payments.com/refund/{payment_id}\")',
            "+        return response.json()",
            "+    except Exception as e:",
            '+        print(\"error\")',
            "+        return None",
            "+",
            "+",
            "+def calculate_tax(amount, region):",
            '+    if region == \"US\":',
            "+        return amount * 0.08",
            '+    elif region == \"EU\":',
            "+        return amount * 0.20",
            '+    elif region == \"UK\":',
            "+        return amount * 0.20",
            "+",
            "+",
            "+def batch_process(payments):",
            "+    results = []",
            "+    for p in payments:",
            "+        result = process_payment(p['user'], p['amount'], p['currency'])",
            "+        results.append(result)",
            "+    return results",
            "+",
            "+",
            "+def get_payment_status(payment_id):",
            '+    if payment_id in cache:',
            "+        return cache[payment_id]",
            "+    response = requests.get(",
            '+        f\"https://api.payments.com/status/{payment_id}\",',
            '+        headers={\"Authorization\": f\"Bearer {API_KEY}\"}',
            "+    )",
            "+    return response.json()",
        ]),
    },
    {
        "filename": "requirements.txt",
        "status": "modified",
        "additions": 8,
        "deletions": 2,
        "patch": "\n".join([
            "@@ -1,2 +1,10 @@",
            "-flask==2.3.0",
            "-requests==2.31.0",
            "+flask",
            "+requests",
            "+pyjwt",
            "+sqlalchemy>=1.4",
            "+pillow",
            "+pyyaml",
            "+jinja2==2.11.0",
            "+urllib3==1.26.5",
        ]),
    },
]


def main():
    # ── Check server ──
    print("=" * 60)
    print("  AI CODE REVIEWER — TEST RUNNER")
    print("=" * 60)

    print("\nChecking server...")
    try:
        r = requests.get(f"{SERVER}/health", timeout=5)
        health = r.json()
        print(f"  Server: {health['status']}")
        print(f"  Tools:  {', '.join(health.get('tools', []))}")
    except requests.ConnectionError:
        print(f"  ERROR: Server not running at {SERVER}")
        print(f"  Start it first:  uvicorn main:app --reload --port 8000")
        sys.exit(1)

    # ── Send test diff ──
    print(f"\nSending test PR diff ({len(TEST_DIFF)} files, ~150 lines of buggy code)...")
    print("This will make 8 LLM calls — expect ~30-60 seconds.\n")

    payload = {
        "diff": json.dumps(TEST_DIFF, indent=2),
        "repo_name": "test/demo-repo",
    }

    start = time.time()
    try:
        response = requests.post(f"{SERVER}/review", json=payload, timeout=300)
    except requests.Timeout:
        print("ERROR: Request timed out after 5 minutes")
        sys.exit(1)

    elapsed = time.time() - start

    if response.status_code != 200:
        print(f"ERROR: Server returned {response.status_code}")
        print(response.text)
        sys.exit(1)

    result = response.json()

    # ── Print results ──
    divider = "-" * 60

    sections = [
        ("CORRECTNESS & RELIABILITY AGENT", "correctness_review"),
        ("SECURITY AGENT", "security_review"),
        ("PERFORMANCE AGENT", "performance_review"),
        ("MAINTAINABILITY AGENT", "maintainability_review"),
        ("DEPENDENCY AGENT", "dependency_review"),
        ("TEST AGENT", "test_review"),
        ("MANAGER DECISION (final review)", "final_review"),
        ("AUTO-FIX SUGGESTIONS", "autofix_suggestions"),
    ]

    for title, key in sections:
        content = result.get(key, "")
        print(f"\n{divider}")
        print(f"  {title}")
        print(divider)
        print(content[:2000] if content else "(empty)")
        if len(content) > 2000:
            print(f"\n  ... ({len(content) - 2000} more chars)")

    # ── Summary ──
    score = result.get("score", "?")
    print(f"\n{'=' * 60}")
    print(f"  REVIEW SCORE: {score}/10")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  LLM calls: 8 (6 agents + manager + scorer)")
    print(f"{'=' * 60}")

    # ── Issue checklist ──
    print("\n  EXPECTED ISSUES — did the agents catch these?")
    print(divider)

    checks = [
        ("Security",        "SQL injection",            ["SQL", "injection", "sql_injection"]),
        ("Security",        "Hardcoded secrets",        ["hardcoded", "secret", "API_KEY", "DB_PASSWORD"]),
        ("Security",        "eval() with user input",   ["eval"]),
        ("Security",        "MD5 for passwords",        ["MD5", "md5", "hash"]),
        ("Security",        "XSS in search_users",      ["XSS", "xss", "unsanitized", "search"]),
        ("Correctness",     "Off-by-one pagination",    ["off-by-one", "offset", "page", "pagination"]),
        ("Correctness",     "Race condition transfer",   ["race", "transaction", "concurrent", "transfer"]),
        ("Correctness",     "Bare except: pass",        ["bare except", "swallow", "silent"]),
        ("Correctness",     "Missing null check",       ["None", "null", "fetchone", "NoneType"]),
        ("Performance",     "N+1 query in orders",      ["N+1", "n+1", "loop", "query"]),
        ("Performance",     "O(n²) find_duplicates",    ["O(n", "quadratic", "nested loop", "n²"]),
        ("Performance",     "Full table load",          ["SELECT *", "fetchall", "entire", "memory"]),
        ("Performance",     "Unbounded cache",          ["cache", "unbounded", "memory leak"]),
        ("Maintainability", "Bad variable names",       ["naming", "d,", "tmp", "variable name"]),
        ("Maintainability", "process_data too complex", ["single responsibility", "too many", "process_data"]),
        ("Backward compat", "get_user signature change",["signature", "breaking", "get_user", "callers"]),
        ("Dependencies",    "Unpinned versions",        ["unpin", "version", "pin"]),
        ("Dependencies",    "Vulnerable jinja2/urllib3",["jinja2", "urllib3", "CVE", "vulnerable"]),
        ("Testing",         "No tests at all",          ["no test", "missing test", "coverage", "zero test"]),
    ]

    final = result.get("final_review", "") + result.get("correctness_review", "") + \
            result.get("security_review", "") + result.get("performance_review", "") + \
            result.get("maintainability_review", "")
    all_text = final.lower()

    found = 0
    missed = 0
    for category, issue, keywords in checks:
        detected = any(kw.lower() in all_text for kw in keywords)
        icon = "✅" if detected else "❌"
        if detected:
            found += 1
        else:
            missed += 1
        print(f"  {icon}  [{category}] {issue}")

    print(divider)
    print(f"  Detected: {found}/{len(checks)}  |  Missed: {missed}/{len(checks)}")
    print()


if __name__ == "__main__":
    main()
