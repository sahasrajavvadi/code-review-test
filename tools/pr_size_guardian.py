def check_pr_size(pr_details: dict, config: dict = None) -> dict:
    """
    Analyze PR size before running the full (expensive) review pipeline.
    Returns a warning if the PR is oversized — large PRs get worse reviews
    because LLMs lose focus in long contexts and reviewers skim.
    """
    max_lines = 500
    max_files = 20

    if config:
        size_config = config.get("pr_size", {})
        max_lines = size_config.get("max_lines", 500)
        max_files = size_config.get("max_files", 20)

    total_additions = pr_details.get("total_additions", 0)
    total_deletions = pr_details.get("total_deletions", 0)
    total_lines = total_additions + total_deletions
    total_files = len(pr_details.get("files", []))

    warnings = []
    if total_lines > max_lines:
        warnings.append(
            f"This PR changes **{total_lines} lines** (recommended max: {max_lines}). "
            "Large PRs are harder to review thoroughly — consider splitting into smaller, "
            "focused PRs (one feature/fix per PR)."
        )
    if total_files > max_files:
        warnings.append(
            f"This PR touches **{total_files} files** (recommended max: {max_files}). "
            "Wide-reaching changes increase the risk of unintended side effects."
        )

    return {
        "total_lines": total_lines,
        "total_additions": total_additions,
        "total_deletions": total_deletions,
        "total_files": total_files,
        "is_oversized": len(warnings) > 0,
        "warnings": warnings,
    }


def format_size_warning(size_check: dict) -> str:
    """Format the PR size warning as a GitHub comment."""
    parts = ["## ⚠️ PR Size Warning\n"]
    for w in size_check["warnings"]:
        parts.append(f"- {w}")
    parts.append(
        f"\n**Stats:** +{size_check['total_additions']} additions, "
        f"-{size_check['total_deletions']} deletions, "
        f"{size_check['total_files']} files changed"
    )
    parts.append("\n> The full AI review will still run, but review quality decreases with PR size.")
    return "\n".join(parts)
