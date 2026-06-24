from supabase import create_client
import os
from datetime import datetime


def get_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def setup_table():
    """
    Run this SQL in Supabase dashboard once:

    CREATE TABLE IF NOT EXISTS review_memory (
        id SERIAL PRIMARY KEY,
        repo_name TEXT NOT NULL,
        pr_number INTEGER NOT NULL,
        review_summary TEXT,
        issue_types TEXT[],
        created_at TIMESTAMP DEFAULT NOW()
    );
    """
    pass


def store_review(repo_name: str, pr_number: int, review: str):
    """Stores a completed review in Supabase memory."""
    try:
        supabase = get_supabase()
        if not supabase:
            print("Warning: Supabase not configured, skipping memory storage")
            return

        # Extract issue types from review
        issue_types = []
        if "SQL" in review or "injection" in review.lower():
            issue_types.append("sql_injection")
        if "password" in review.lower() or "secret" in review.lower():
            issue_types.append("hardcoded_secret")
        if "loop" in review.lower() and "query" in review.lower():
            issue_types.append("n_plus_1_query")
        if "performance" in review.lower():
            issue_types.append("performance")
        if "style" in review.lower() or "naming" in review.lower():
            issue_types.append("style")
        if "authentication" in review.lower() or "auth" in review.lower():
            issue_types.append("auth")

        supabase.table("review_memory").insert({
            "repo_name": repo_name,
            "pr_number": pr_number,
            "review_summary": review[:500],
            "issue_types": issue_types,
            "created_at": datetime.now().isoformat()
        }).execute()

        print(f"💾 Review stored in memory for {repo_name}")

    except Exception as e:
        print(f"Warning: Could not store review in memory: {e}")


def get_past_issues(repo_name: str) -> list:
    """Retrieves what issues this team has had before."""
    try:
        supabase = get_supabase()
        if not supabase:
            return []

        result = supabase.table("review_memory")\
            .select("issue_types")\
            .eq("repo_name", repo_name)\
            .order("created_at", desc=True)\
            .limit(10)\
            .execute()

        if not result.data:
            return []

        # Flatten all issue types
        all_issues = []
        for row in result.data:
            types = row.get("issue_types") or []
            all_issues.extend(types)

        # Return unique issues
        unique_issues = list(set(all_issues))
        print(f"🧠 Past issues for {repo_name}: {unique_issues}")
        return unique_issues

    except Exception as e:
        print(f"Warning: Could not fetch memory: {e}")
        return []
