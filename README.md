# AI Code Review Agent

Multi-agent AI system that automatically reviews GitHub Pull Requests using 6 specialist agents backed by real static-analysis tools.

## What Happens When You Open a PR

```
PR Opened → Webhook → Clone PR → Run 5 Tools → 6 AI Agents (parallel) → Manager Decision → GitHub Comment
```

1. **PR Size Guardian** — warns if PR is too large (>500 lines)
2. **5 Static Analysis Tools** run in parallel on the actual code:
   - `bandit` (security) · `ruff` (linting) · `detect-secrets` (credentials) · `pip-audit` (CVEs) · `radon` (complexity) · `eslint` (JS/TS)
3. **6 AI Agents** review the diff + tool output in parallel:
   - **Correctness** — logic bugs, edge cases, failure handling, race conditions, backward compatibility
   - **Security** — injection, auth bypass, secrets, with concrete attack scenarios
   - **Performance** — N+1 queries, memory, O(n²), "what breaks at 100x scale"
   - **Maintainability** — readability, SRP, duplication, codebase consistency
   - **Dependency** — vulnerable packages, unpinned versions, typosquatting
   - **Test Coverage** — missing tests, edge cases, regression safety
4. **Manager Agent** reads all 6 reviews → makes a **MERGE / BLOCK** decision
5. **Auto-Fix Agent** generates one-click code fix suggestions
6. **Smart Reviewer Assignment** suggests who should review based on git history
7. Posts: **inline comments** (per-line) + **summary comment** + **commit status check** (pass/fail)

## Tech Stack

| Tool | Purpose |
|------|---------|
| LangGraph | Multi-agent orchestration (fan-out/fan-in) |
| Groq (Llama 3.3 70B) | Primary LLM (free tier) |
| Gemini 2.0 Flash | Fallback LLM (free tier) |
| bandit / ruff / radon / detect-secrets / pip-audit / eslint | Static analysis tools |
| ChromaDB | RAG — codebase style context |
| Supabase | Memory — learns from past reviews |
| FastAPI | Webhook server |
| LangSmith | Tracing and observability |
| PyGithub | GitHub API integration |

## Setup

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/ai-code-reviewer.git
cd ai-code-reviewer
pip install -r requirements.txt
```

### 2. Get your API keys (all free)

| Key | Where to get it |
|-----|----------------|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) → API Keys |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com/apikey) |
| `GITHUB_TOKEN` | [github.com/settings/tokens](https://github.com/settings/tokens) → Generate new token (classic) → select `repo` scope |
| `GITHUB_WEBHOOK_SECRET` | Any random string you choose (e.g. `my-secret-123`) |
| `LANGSMITH_API_KEY` | [smith.langchain.com](https://smith.langchain.com) → Settings → API Keys |
| `SUPABASE_URL` | [supabase.com](https://supabase.com) → Create project → Settings → API → URL |
| `SUPABASE_KEY` | Same page → `anon` `public` key |

### 3. Create your `.env` file

```bash
cp .env.example .env
# Then edit .env with your keys
```

### 4. Setup Supabase table

Run this SQL in your Supabase dashboard (SQL Editor):

```sql
CREATE TABLE IF NOT EXISTS review_memory (
    id SERIAL PRIMARY KEY,
    repo_name TEXT NOT NULL,
    pr_number INTEGER NOT NULL,
    review_summary TEXT,
    issue_types TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 5. Start the server

```bash
uvicorn main:app --reload --port 8000
```

### 6. Expose to GitHub with ngrok

```bash
ngrok http 8000
```

Copy the `https://xxxx.ngrok-free.app` URL.

### 7. Add webhook to your GitHub repo

1. Go to your repo → **Settings** → **Webhooks** → **Add webhook**
2. **Payload URL:** `https://xxxx.ngrok-free.app/webhook`
3. **Content type:** `application/json`
4. **Secret:** same value as your `GITHUB_WEBHOOK_SECRET` in `.env`
5. **Events:** select **Pull requests** only
6. Click **Add webhook**

### 8. Test it — create a PR with bad code

Create a new branch, add a buggy file, push, and open a PR:

```bash
git checkout -b test-review
```

Create a file `test_bad_code.py` with intentional bugs:

```python
import sqlite3
import hashlib

DB_PASSWORD = "admin123"
conn = sqlite3.connect("app.db")

def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    return conn.execute(query).fetchone()

def transfer(from_id, to_id, amount):
    bal = conn.execute(f"SELECT balance FROM users WHERE id = '{from_id}'").fetchone()[0]
    conn.execute(f"UPDATE users SET balance = {bal - amount} WHERE id = '{from_id}'")
    conn.execute(f"UPDATE users SET balance = balance + {amount} WHERE id = '{to_id}'")
    conn.commit()

def find_dupes(users):
    dupes = []
    for i in range(len(users)):
        for j in range(len(users)):
            if i != j and users[i] == users[j]:
                dupes.append(users[i])
    return dupes

def process(d):
    x = d.get('v')
    result = eval(d.get('formula', '0'))
    return result

def hash_pw(pw):
    return hashlib.md5(pw.encode()).hexdigest()
```

Then push and create a PR:

```bash
git add test_bad_code.py
git commit -m "Add user service"
git push -u origin test-review
```

Go to GitHub and create a Pull Request. The bot will automatically review it within ~60 seconds.

## Manual Testing (without GitHub webhook)

### Quick test with the test script

```bash
python test_review.py
```

This sends a pre-built buggy diff to `/review` and checks if all agents caught the planted issues.

### Test with curl

```bash
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d '{"diff": "password = admin123\nquery = f\"SELECT * FROM users WHERE id = {user_input}\"", "repo_name": "test/repo"}'
```

### Health check

```bash
curl http://localhost:8000/health
```

### Dashboard

Open `http://localhost:8000/dashboard` in a browser (requires Supabase).

## Docker Deployment

```bash
docker-compose up --build
```

## Per-Repo Configuration

Create `.ai-reviewer.yml` in your repo root to customize:

```yaml
agents:
  correctness: true
  security: true
  performance: true
  maintainability: true
  dependency: true
  test: true
  autofix: true

severity_threshold: MEDIUM

ignore:
  - "tests/*"
  - "docs/*"
  - "*.md"

pr_size:
  max_lines: 500
  max_files: 20
```

## Architecture

```
              ┌─► correctness ──────────────────┐
              ├─► security (bandit+secrets) ────┤
START ────────┼─► performance (radon) ──────────┼──► manager ──┬─► autofix ──► END
              ├─► maintainability (ruff/eslint) ┤             └─► scorer  ──► END
              ├─► dependency (pip-audit) ───────┤
              └─► test ─────────────────────────┘
```

## Project Structure

```
ai-code-reviewer/
├── agents/
│   ├── correctness_agent.py    # Logic bugs, failure handling, concurrency, backward compat
│   ├── security_agent.py       # Injection, auth, secrets — with attack scenarios
│   ├── performance_agent.py    # N+1, memory, O(n²), "what breaks at 100x"
│   ├── maintainability_agent.py # Readability, SRP, duplication, consistency
│   ├── dependency_agent.py     # CVEs, unpinned versions, supply chain
│   ├── test_agent.py           # Coverage gaps, edge cases, regression safety
│   ├── autofix_agent.py        # Generates one-click code fix suggestions
│   └── critic_agent.py         # Manager — MERGE/BLOCK decision + scoring
├── tools/
│   ├── bandit_runner.py        # Python security scanner
│   ├── ruff_runner.py          # Python linter
│   ├── secret_scanner.py       # detect-secrets for hardcoded creds
│   ├── dependency_scanner.py   # pip-audit for vulnerable deps
│   ├── complexity_analyzer.py  # radon cyclomatic complexity
│   ├── eslint_runner.py        # ESLint for JS/TS
│   ├── pr_size_guardian.py     # Warns on oversized PRs
│   ├── breaking_change_detector.py  # Detects removed APIs
│   ├── git_history_analyzer.py # Hotspot file detection
│   ├── reviewer_assignment.py  # Suggests reviewers from git history
│   ├── repo_manager.py         # Clones PR into temp workspace
│   ├── runner.py               # Orchestrates all tools in parallel
│   └── base.py                 # Finding/ToolResult dataclasses
├── core/
│   ├── github_handler.py       # GitHub API — comments, inline reviews, status checks
│   ├── llm_provider.py         # Groq → Gemini failover with retry
│   ├── rag_pipeline.py         # ChromaDB vector store
│   ├── memory.py               # Supabase review memory
│   ├── security.py             # HMAC webhook signature verification
│   ├── config.py               # Per-repo .ai-reviewer.yml config
│   └── dashboard.py            # Review dashboard with charts
├── graph/
│   └── review_graph.py         # LangGraph — 6-way fan-out/fan-in
├── main.py                     # FastAPI server — webhook + review + dashboard
├── test_review.py              # Test script with 19 planted bugs
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── .gitignore
```

## Research Backing

- Rasheed et al. (2024) — *AI-powered Code Review with LLMs: Early Results* — Tampere University
- Collante et al. (2025) — *The Impact of LLMs on Code Review Process* — Concordia University
- Kumar & Chimalakonda (2024) — *Code Review Automation via Multi-task Federated LLM* — IIT Tirupati
