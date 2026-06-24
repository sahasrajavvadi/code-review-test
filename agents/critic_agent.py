from core.llm_provider import get_llm_response


def critic_agent(
    correctness_review: str,
    security_review: str,
    performance_review: str,
    maintainability_review: str,
    dependency_review: str = "",
    test_review: str = "",
) -> str:
    """
    Manager Agent — the final decision-maker. Takes all specialist reviews,
    deduplicates, removes false positives, and makes the merge/block call
    like a senior engineering manager deciding whether to ship.
    """
    prompt = f"""You are the engineering manager making the final call on this pull request.
A developer is asking you: "Can we push this to production?"

You have reviews from 6 specialist agents, each backed by real static-analysis tools.
Read ALL of them carefully, then make your decision.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CORRECTNESS & RELIABILITY REVIEW:
{correctness_review}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECURITY REVIEW (bandit + detect-secrets):
{security_review}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PERFORMANCE REVIEW (radon complexity analysis):
{performance_review}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MAINTAINABILITY REVIEW (ruff linter):
{maintainability_review}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DEPENDENCY REVIEW (pip-audit vulnerability scan):
{dependency_review or "No dependency review available."}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TEST COVERAGE REVIEW:
{test_review or "No test review available."}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

YOUR TASKS:
1. DEDUPLICATE — Remove the same issue flagged by multiple agents
2. FILTER — Remove false positives and theoretical risks without concrete exploit/failure paths
3. RANK — Order by production impact (what causes an incident vs what's just ugly)
4. DECIDE — Make the merge call using the framework below

DECISION FRAMEWORK:

🔴 BLOCK MERGE if ANY of these exist:
- Correctness bugs that will produce wrong results in production
- Security vulnerabilities with a concrete attack vector
- Missing error handling on critical paths that will cause 500s, data loss, or silent corruption
- Breaking changes to existing APIs/contracts without a migration plan
- Known vulnerable dependencies with HIGH/CRITICAL CVEs

🟡 APPROVE WITH REQUIRED CHANGES if:
- Performance issues that will degrade at realistic production scale
- Missing tests for new critical code paths (new endpoints, data mutations)
- Error handling exists but is poor (swallows errors, logs without context)
- Concurrency concerns in code that will face concurrent access

🟢 APPROVE (with optional suggestions) if:
- Only style/naming/readability improvements remain
- Minor test gaps on non-critical paths
- Nice-to-have performance optimizations
- Documentation improvements

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

## 🤖 AI Code Review

### 🚦 Verdict: [BLOCK MERGE ❌ / APPROVE WITH CHANGES ⚠️ / APPROVE ✅]
> [One sentence: why this decision. Be direct.]

### 🔴 Must Fix Before Merge
[If none, write "None — no blocking issues found."]
- **[Issue title]** ([file:line]): [What's wrong, why it matters, exact fix]

### 🟡 Should Fix
[If none, write "None."]
- **[Issue title]** ([file:line]): [What's wrong, impact, fix]

### 🟢 Consider Improving
[If none, write "None."]
- **[Issue title]**: [Suggestion]

### 📊 Review Summary
| Dimension | Status | Key Finding |
|-----------|--------|-------------|
| Correctness | ✅/⚠️/❌ | [one line] |
| Security | ✅/⚠️/❌ | [one line] |
| Performance | ✅/⚠️/❌ | [one line] |
| Maintainability | ✅/⚠️/❌ | [one line] |
| Dependencies | ✅/⚠️/❌ | [one line] |
| Test Coverage | ✅/⚠️/❌ | [one line] |

### ✅ What's Done Well
[Always include 1-2 genuine positives — what the developer did right]

---
*Reviewed by AI Code Review Agent — 6 specialist agents + 5 static analysis tools*
*Tools: bandit · ruff · detect-secrets · pip-audit · radon*"""

    result = get_llm_response(prompt)
    print(f"⚡ Manager Agent done: {len(result)} chars")
    return result


def score_review(review: str) -> str:
    """LLM-as-judge — scores the final review on the qualities that make reviews useful."""
    prompt = f"""Rate this code review from 1 to 10.

A 10/10 review:
- Identifies real issues with concrete failure scenarios, not vague concerns
- Every finding is actionable — the developer knows EXACTLY what to change
- Distinguishes blocking issues from nice-to-haves (correct severity ranking)
- References actual tool findings to back up claims
- Professional tone — direct but respectful, no condescension
- Makes a clear merge/block decision with sound reasoning
- Acknowledges what the developer did well

A 1/10 review:
- Vague ("this could be improved"), theoretical ("might have issues"), or wrong
- Lists issues without fixes
- Everything is HIGH severity
- Misses obvious bugs while flagging style nits

Review to rate:
{review}

Respond with ONLY a number between 1 and 10. Nothing else."""

    return get_llm_response(prompt).strip()
