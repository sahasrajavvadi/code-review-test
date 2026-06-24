from core.llm_provider import get_llm_response


def autofix_agent(diff: str, final_review: str) -> str:
    """
    Reads the manager's review and the original diff, generates concrete
    code fixes in GitHub's suggested-changes format so developers can
    accept each fix with one click.
    """
    prompt = f"""You are a senior engineer generating one-click code fixes for review findings.

MANAGER'S REVIEW (contains the issues to fix):
{final_review}

ORIGINAL CODE DIFF:
{diff}

RULES:
1. Only generate fixes for issues that have a single, clear, correct solution.
2. Skip style-only issues (naming, formatting) — those are subjective.
3. Focus on: security fixes, bug fixes, missing error handling, performance fixes.
4. For each fix, quote the EXACT original line(s) from the diff and provide the corrected version.
5. If an issue requires a design-level change (restructuring, new classes), skip it — those
   can't be expressed as a line-level patch.

Format EACH fix EXACTLY like this:

### Fix: [short title]
**File:** `[filename]`  |  **Line:** [line number]

Original code:
```
[exact original code line(s) from the diff]
```

Suggested fix:
```suggestion
[corrected code line(s)]
```

**Why:** [one sentence — what this fixes and why it matters]

---

If NO issues can be auto-fixed (all require design changes), respond with:
### No Auto-Fixes Available
All identified issues require design-level changes that cannot be expressed as line-level patches.
Apply the suggestions from the review manually.

Generate fixes for as many actionable findings as possible."""

    result = get_llm_response(prompt)
    print(f"🔧 Auto-Fix Agent done: {len(result)} chars")
    return result
