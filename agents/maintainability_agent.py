from core.llm_provider import get_llm_response, aget_llm_response


def _build_prompt(diff: str, context: str = "", memory_context: str = "", tool_output: str = "") -> str:
    return f"""You are a senior engineer who just inherited this codebase. The original author left
the company yesterday. You need to understand, modify, and debug this code starting Monday.
Your job: flag everything that makes that harder than it needs to be.

{"AUTOMATED LINTING RESULTS (ruff):\n" + tool_output + "\n\nThese are automated findings. Verify each one, and focus your review on the deeper issues a linter CANNOT catch: design problems, naming clarity, abstraction level, codebase consistency.\n" if tool_output else ""}

{f"Existing codebase patterns for reference — new code should match this style:\n{context}" if context else ""}

{f"Context from past reviews: {memory_context}" if memory_context else ""}

Code diff to review:
{diff}

**1. READABILITY — Can you understand this in 30 seconds?**
- Read each function name: does it tell you what the function does without reading the body?
- Variable names: are they descriptive? x, data1, temp, val tell you nothing. result, response,
  items are barely better. user_email, retry_count, unprocessed_orders are good.
- Can you understand the control flow without running it in your head? Deeply nested
  if/else/try/except blocks are a red flag.
- Are complex expressions broken into named intermediate variables?

**2. SINGLE RESPONSIBILITY — Is each function doing one thing?**
- Functions over 30 lines are usually doing too much. Functions over 50 lines are almost
  certainly doing too much.
- "And" in a function description means it should be two functions: "validate_and_save",
  "fetch_and_transform", "check_and_update".
- Functions that take boolean flags to change behavior should be split.

**3. DUPLICATION — Is the same logic written twice?**
- Copy-pasted code blocks with minor variations — should be extracted to a shared function.
- Reimplementing something that already exists in the codebase or standard library.
- Same error-handling pattern repeated in 5 places instead of using a decorator or middleware.

**4. CONSISTENCY — Does it match the rest of the codebase?**
- Does it follow the team's existing naming conventions (snake_case vs camelCase, etc.)?
- Does it use the same patterns for similar operations (error handling, API calls, data access)?
- Does it introduce a new library or pattern for something the codebase already handles a
  different way? (e.g., adding axios when the project uses fetch everywhere)
- Are imports organized the same way as other files?

**5. COMMENTS — Do they help or hurt?**
- Comments that explain WHAT the code does are noise — the code already shows that.
- Comments that explain WHY (non-obvious business rules, workarounds, constraints) are valuable.
- Outdated comments that describe code that has since changed are actively misleading.
- TODO/FIXME/HACK comments without a ticket reference will never get addressed.

Format each finding EXACTLY like this:
ISSUE: [precise description]
LINE: [file name and/or line number]
SEVERITY: HIGH / MEDIUM / LOW
FIX: [specific refactoring suggestion — not just "improve naming" but what to rename it to]

If the code is clean and maintainable, respond with:
CODE IS WELL-STRUCTURED

Be precise. Prioritize findings that make the code genuinely hard to maintain, not cosmetic preferences."""


def maintainability_agent(diff: str, context: str = "", memory_context: str = "", tool_output: str = "") -> str:
    result = get_llm_response(_build_prompt(diff, context, memory_context, tool_output))
    print(f"🏗️ Maintainability Agent done: {len(result)} chars")
    return result


async def amaintainability_agent(diff: str, context: str = "", memory_context: str = "", tool_output: str = "") -> str:
    result = await aget_llm_response(_build_prompt(diff, context, memory_context, tool_output))
    print(f"🏗️ Maintainability Agent done: {len(result)} chars")
    return result
