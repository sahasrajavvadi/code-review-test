import os
from collections import Counter


def suggest_reviewers(repo_name: str, changed_files: list, pr_author: str) -> list:
    """
    Analyze git history via GitHub API to find who knows each changed file best.
    Returns the top 3 contributors (excluding the PR author) as suggested reviewers.
    """
    from github import Github

    g = Github(os.getenv("GITHUB_TOKEN"))
    repo = g.get_repo(repo_name)

    contributor_counts = Counter()
    file_expertise = {}

    for filename in changed_files[:10]:
        try:
            commits = list(repo.get_commits(path=filename))[:20]
            for commit in commits:
                author = commit.author
                if author and author.login and author.login != pr_author:
                    contributor_counts[author.login] += 1
                    file_expertise.setdefault(author.login, [])
                    if filename not in file_expertise[author.login]:
                        file_expertise[author.login].append(filename)
        except Exception:
            continue

    suggested = []
    for login, count in contributor_counts.most_common(3):
        suggested.append({
            "login": login,
            "file_touches": count,
            "knows_files": file_expertise.get(login, [])[:5],
        })

    return suggested


def format_reviewer_suggestion(reviewers: list) -> str:
    """Format reviewer suggestions as a GitHub comment section."""
    if not reviewers:
        return ""
    lines = ["\n### 👥 Suggested Reviewers"]
    lines.append("Based on git history — who knows this code best:\n")
    for r in reviewers:
        files = ", ".join(f"`{f}`" for f in r["knows_files"][:3])
        lines.append(f"- **@{r['login']}** — {r['file_touches']} commits touching: {files}")
    return "\n".join(lines)
