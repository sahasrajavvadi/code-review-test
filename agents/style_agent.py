from core.llm_provider import get_llm_response, aget_llm_response


def _build_prompt(diff: str, context: str = "", memory_context: str = "", tool_output: str = "") -> str:
    return f"""You are a senior code quality engineer with 10+ years of experience.
Your ONLY job is to find code style and quality issues in this code diff.

{"LINTING RESULTS (from ruff):\n" + tool_output + "\n\nVerify each finding and add any style/quality issues the linter cannot catch (design problems, naming clarity, abstraction level).\n" if tool_output else ""}

{f"Existing codebase style for reference (match new code to this):\n{context}" if context else "No existing codebase context available."}

{f"Note from memory: {memory_context}" if memory_context else ""}

Code diff to review:
{diff}

Look specifically for:
1. Naming conventions - are variable/function names clear and consistent?
2. Function length - functions doing too many things (should be single responsibility)
3. Missing error handling - no try/except where needed
4. Code duplication - same logic repeated instead of reusing
5. Missing docstrings or comments for complex logic
6. Dead code - unused variables or imports
7. Magic numbers - hardcoded numbers without explanation
8. Inconsistency with existing codebase style

Format each issue EXACTLY like this:
ISSUE: [clear description of the problem]
LINE: [line number or file name]
SEVERITY: HIGH / MEDIUM / LOW
FIX: [exact code fix or suggestion]

If you find NO style issues, respond with exactly:
NO STYLE ISSUES FOUND

Be precise. Do not repeat yourself. Only report real issues."""


def style_agent(diff: str, context: str = "", memory_context: str = "", tool_output: str = "") -> str:
    result = get_llm_response(_build_prompt(diff, context, memory_context, tool_output))
    print(f"🟢 Style Agent done: {len(result)} chars")
    return result


async def astyle_agent(diff: str, context: str = "", memory_context: str = "", tool_output: str = "") -> str:
    result = await aget_llm_response(_build_prompt(diff, context, memory_context, tool_output))
    print(f"🟢 Style Agent done: {len(result)} chars")
    return result
