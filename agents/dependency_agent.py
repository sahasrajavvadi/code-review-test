from core.llm_provider import get_llm_response, aget_llm_response


def _build_prompt(diff: str, tool_output: str = "", memory_context: str = "") -> str:
    return f"""You are a senior DevSecOps engineer specializing in supply-chain security.
Your ONLY job is to review dependency changes in this code diff for security risks.

{"AUTOMATED VULNERABILITY SCAN RESULTS (from pip-audit):\n" + tool_output + "\n\nVerify each finding against the diff. Add any issues the scanner missed.\n" if tool_output else "No automated scan available — analyze dependencies manually from the diff.\n"}

{f"Note from memory: {memory_context}" if memory_context else ""}

Code diff to review:
{diff}

Look specifically for:
1. Known vulnerable dependencies — outdated packages with published CVEs
2. Unpinned versions — using >= or no version pin (supply-chain risk)
3. Typosquatting — package names that look like misspellings of popular packages
4. Unnecessary dependencies — packages that add attack surface without clear need
5. License compatibility issues — AGPL/GPL in a proprietary project
6. Deprecated packages — libraries that are no longer maintained

Format each issue EXACTLY like this:
ISSUE: [clear description]
PACKAGE: [package name and version]
SEVERITY: HIGH / MEDIUM / LOW
FIX: [exact fix — upgraded version, alternative package, or removal]

If you find NO dependency issues, respond with exactly:
NO DEPENDENCY ISSUES FOUND

Be precise. Do not repeat yourself. Only report real issues."""


def dependency_agent(diff: str, tool_output: str = "", memory_context: str = "") -> str:
    result = get_llm_response(_build_prompt(diff, tool_output, memory_context))
    print(f"📦 Dependency Agent done: {len(result)} chars")
    return result


async def adependency_agent(diff: str, tool_output: str = "", memory_context: str = "") -> str:
    try:
        result = await aget_llm_response(_build_prompt(diff, tool_output, memory_context))
        print(f"📦 Dependency Agent done: {len(result)} chars")
        return result
    except Exception as e:
        print(f"📦 Dependency Agent failed: {e}")
        return "Unable to complete dependency review due to service error. Manual review recommended."
