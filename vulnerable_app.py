import sqlite3
import hashlib
import requests

# Hardcoded credentials
DB_PASSWORD = "super_secret_123"
API_KEY = "sk-live-a1b2c3d4e5f6g7h8i9j0"

conn = sqlite3.connect("production.db")


def get_user(user_id):
    # SQL injection - user input directly in query
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    return conn.execute(query).fetchone()


def login(username, password):
    # SQL injection + MD5 for password hashing
    pw_hash = hashlib.md5(password.encode()).hexdigest()
    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{pw_hash}'"
    user = conn.execute(query).fetchone()
    return user


def transfer_money(from_id, to_id, amount):
    # Race condition - no transaction, no balance check
    balance = conn.execute(
        f"SELECT balance FROM accounts WHERE user_id = '{from_id}'"
    ).fetchone()[0]
    conn.execute(
        f"UPDATE accounts SET balance = {balance - amount} WHERE user_id = '{from_id}'"
    )
    conn.execute(
        f"UPDATE accounts SET balance = balance + {amount} WHERE user_id = '{to_id}'"
    )
    conn.commit()


def search(query):
    # XSS - unsanitized user input in HTML
    return f"<h1>Results for: {query}</h1>"


def list_users(page, limit):
    # Off-by-one: page 1 skips first row
    offset = page * limit
    # Loads ALL users then slices in Python
    all_users = conn.execute("SELECT * FROM users").fetchall()
    return all_users[offset:offset + limit]


def find_duplicates(users):
    # O(n squared) when a set would work
    dupes = []
    for i in range(len(users)):
        for j in range(len(users)):
            if i != j and users[i]['email'] == users[j]['email']:
                dupes.append(users[i])
    return dupes


def delete_user(user_id):
    try:
        conn.execute(f"DELETE FROM users WHERE id = '{user_id}'")
        conn.commit()
    except:
        pass  # silently swallow all errors


def run_formula(data):
    # eval with user input - remote code execution
    return eval(data.get('formula', '0'))


def process_payment(user_id, amount):
    # No timeout, no error handling, no input validation
    response = requests.post(
        "https://api.payments.com/charge",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"user": user_id, "amount": amount}
    )
    return response.json()


cache = {}  # unbounded global cache - memory leak


def get_status(payment_id):
    cache[payment_id] = requests.get(
        f"https://api.payments.com/{payment_id}"
    ).json()
    return cache[payment_id]
