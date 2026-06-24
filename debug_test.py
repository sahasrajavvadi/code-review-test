import requests
import json
import sys

SERVER = "http://localhost:8000"

# Simple test diff
TEST_DIFF = [
    {
        "filename": "test.py",
        "status": "modified",
        "additions": 5,
        "deletions": 0,
        "patch": """@@ -0,0 +1,5 @@
+def hello():
+    print("hello")
+
+if __name__ == "__main__":
+    hello()
"""
    }
]

# Check server
print("Checking server...")
try:
    r = requests.get(f"{SERVER}/health", timeout=5)
    print(f"Server health: {r.status_code}")
except Exception as e:
    print(f"Server error: {e}")
    sys.exit(1)

# Send test request
print("\nSending review request...")
payload = {
    "diff": json.dumps(TEST_DIFF, indent=2),
    "repo_name": "test/demo",
}

try:
    response = requests.post(f"{SERVER}/review", json=payload, timeout=30)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:2000]}")
except requests.Timeout:
    print("Request timed out")
except Exception as e:
    print(f"Error: {e}")
