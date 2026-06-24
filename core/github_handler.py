from github import Github
import os


def get_github_client():
    return Github(os.getenv("GITHUB_TOKEN"))


def get_pr_details(repo_name: str, pr_number: int) -> dict:
    """Fetch PR diff, metadata, and head SHA from GitHub."""
    g = get_github_client()
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    files_changed = []
    for file in pr.get_files():
        files_changed.append({
            "filename": file.filename,
            "patch": file.patch if file.patch else "Binary file or no changes",
            "additions": file.additions,
            "deletions": file.deletions,
            "status": file.status,
        })

    return {
        "pr_number": pr_number,
        "pr_title": pr.title,
        "pr_body": pr.body or "",
        "author": pr.user.login,
        "files": files_changed,
        "total_additions": pr.additions,
        "total_deletions": pr.deletions,
        "head_sha": pr.head.sha,
    }


def post_pr_comment(repo_name: str, pr_number: int, comment: str):
    """Post a summary comment on the GitHub PR."""
    g = get_github_client()
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    pr.create_issue_comment(comment)
    print(f"  ✅ Comment posted on PR #{pr_number}")


def post_inline_comments(repo_name: str, pr_number: int, findings: list):
    """Post review comments on specific lines of changed files."""
    if not findings:
        return

    try:
        g = get_github_client()
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        commit = repo.get_commit(pr.head.sha)

        comments = []
        for finding in findings[:25]:
            body = f"**{finding.get('severity', 'INFO')}**: {finding.get('message', '')}"
            if finding.get("suggestion"):
                body += f"\n\n**Suggested fix**: {finding['suggestion']}"

            line = finding.get("line", 1)
            if line < 1:
                continue

            comments.append({
                "path": finding["file"],
                "line": line,
                "body": body,
            })

        if comments:
            pr.create_review(
                commit=commit,
                body="AI Code Review — inline findings from static analysis tools (bandit, ruff, detect-secrets, pip-audit, radon)",
                comments=comments,
                event="COMMENT",
            )
            print(f"  ✅ Posted {len(comments)} inline comments on PR #{pr_number}")

    except Exception as e:
        print(f"  ⚠️ Could not post inline comments (falling back to summary only): {e}")


def post_pr_status(repo_name: str, head_sha: str, state: str, description: str):
    """Set a commit status check (pending/success/failure) on the PR head."""
    try:
        g = get_github_client()
        repo = g.get_repo(repo_name)
        commit = repo.get_commit(head_sha)
        commit.create_status(
            state=state,
            description=description[:140],
            context="AI Code Reviewer",
        )
        print(f"  ✅ Status '{state}' set on {head_sha[:7]}")
    except Exception as e:
        print(f"  ⚠️ Could not set commit status: {e}")


def get_repo_files(repo_name: str, max_files: int = 20) -> list:
    """Fetch Python files from repo for RAG ingestion."""
    g = get_github_client()
    repo = g.get_repo(repo_name)

    files = []
    try:
        contents = repo.get_contents("")
        count = 0

        while contents and count < max_files:
            file_content = contents.pop(0)

            if file_content.type == "dir":
                contents.extend(repo.get_contents(file_content.path))
            elif file_content.name.endswith(".py"):
                try:
                    content = file_content.decoded_content.decode("utf-8")
                    files.append({
                        "name": file_content.path,
                        "content": content[:2000],
                    })
                    count += 1
                except Exception:
                    pass

    except Exception as e:
        print(f"Warning: Could not fetch repo files: {e}")

    print(f"  📁 Fetched {len(files)} files from {repo_name}")
    return files
