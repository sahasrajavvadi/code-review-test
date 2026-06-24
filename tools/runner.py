import asyncio

from .bandit_runner import run_bandit
from .complexity_analyzer import run_complexity_analysis
from .dependency_scanner import run_dependency_scan
from .eslint_runner import run_eslint
from .ruff_runner import run_ruff
from .secret_scanner import run_secret_scan
from .base import ToolResult


async def run_all_tools(workspace_dir: str, changed_files: list, config: dict = None) -> dict:
    """
    Run all relevant static-analysis tools in parallel on the PR workspace.

    Language detection: scans changed file extensions and only runs tools for
    languages present in the PR. Python-only PRs skip ESLint, JS-only PRs
    skip bandit/ruff/radon, mixed PRs run everything.

    Workspace lifecycle is managed by the caller (main.py), not here.
    """
    filenames = [f["filename"] for f in changed_files if isinstance(f, dict)]

    if config:
        from core.config import should_ignore
        filenames = [f for f in filenames if not should_ignore(f, config)]

    has_python = any(f.endswith(".py") for f in filenames)
    has_js = any(f.endswith((".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs")) for f in filenames)

    tasks = []
    names = []

    # Python tools
    if has_python:
        tasks.extend([
            asyncio.to_thread(run_bandit, workspace_dir, filenames),
            asyncio.to_thread(run_ruff, workspace_dir, filenames),
            asyncio.to_thread(run_complexity_analysis, workspace_dir, filenames),
        ])
        names.extend(["bandit", "ruff", "radon"])

    # JS/TS tools
    if has_js:
        tasks.append(asyncio.to_thread(run_eslint, workspace_dir, filenames))
        names.append("eslint")

    # Language-agnostic tools (always run)
    tasks.append(asyncio.to_thread(run_secret_scan, workspace_dir, filenames))
    names.append("detect-secrets")

    tasks.append(asyncio.to_thread(run_dependency_scan, workspace_dir))
    names.append("pip-audit")

    if not tasks:
        return {}

    results = await asyncio.gather(*tasks, return_exceptions=True)

    tool_results = {}
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            tool_results[name] = ToolResult(tool_name=name, success=False, error=str(result))
        else:
            tool_results[name] = result

    return tool_results
