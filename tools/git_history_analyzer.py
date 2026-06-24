import os
from datetime import datetime, timedelta


def analyze_git_history(repo_name: str, changed_files: list) -> dict:
    """
    Query GitHub API for commit history on changed files.
    Identifies "hotspot" files — ones that keep getting bug fixes,
    signaling the code is fragile and needs extra scrutiny.
    """
    from github import Github

    g = Github(os.getenv("GITHUB_TOKEN"))
    repo = g.get_repo(repo_name)
    since = datetime.now() - timedelta(days=90)

    hotspots = []
    fix_keywords = {"fix", "bug", "hotfix", "patch", "resolve", "crash", "error", "broken"}

    for filename in changed_files[:10]:
        try:
            commits = list(repo.get_commits(path=filename, since=since))
            total = len(commits)
            if total == 0:
                continue

            fixes = sum(
                1 for c in commits
                if any(kw in c.commit.message.lower() for kw in fix_keywords)
            )

            if total >= 5 or fixes >= 2:
                hotspots.append({
                    "file": filename,
                    "total_commits_3mo": total,
                    "fix_commits_3mo": fixes,
                    "risk": "HIGH" if fixes >= 3 else "MEDIUM",
                })
        except Exception:
            continue

    return {
        "hotspots": hotspots,
        "to_prompt_text": _format_for_prompt(hotspots),
    }


def _format_for_prompt(hotspots: list) -> str:
    if not hotspots:
        return ""
    lines = ["HOTSPOT FILES (frequently changed/fixed — review with extra scrutiny):"]
    for h in hotspots:
        lines.append(
            f"  - {h['file']}: {h['total_commits_3mo']} commits, "
            f"{h['fix_commits_3mo']} bug-fix commits in last 3 months ({h['risk']} risk)"
        )
    return "\n".join(lines)
