import sqlite3

API_KEY = "sk-test-12345-hardcoded-secret"


def get_user(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(query)
    return cursor.fetchone()


def get_all_user_orders(user_ids):
    results = []
    for uid in user_ids:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE user_id = " + uid)
        results.append(cursor.fetchone())
    return results


def calc(a, b, c, d, e, f):
    x = a + b
    y = x * c
    z = y - d
    w = z / e
    v = w + f
    return v
