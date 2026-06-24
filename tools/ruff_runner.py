import json
import os
import subprocess

from .base import Finding, ToolResult


def run_ruff(workspace_dir: str, changed_files: list) -> ToolResult:
    """Run the ruff linter on changed Python files."""
    py_files = [f for f in changed_files if f.endswith(".py")]
    if not py_files:
        return ToolResult(tool_name="ruff", success=True, summary="No Python files to lint.")

    try:
        targets = [
            os.path.join(workspace_dir, f) for f in py_files
            if os.path.exists(os.path.join(workspace_dir, f))
        ]
        if not targets:
            return ToolResult(tool_name="ruff", success=True)

        result = subprocess.run(
            ["ruff", "check", "--output-format", "json"] + targets,
            capture_output=True, text=True, timeout=60,
        )

        data = json.loads(result.stdout or "[]")
        findings = []
        for issue in data:
            code = issue.get("code", "")
            if code.startswith(("E9", "F8", "F6")):
                sev = "HIGH"
            elif code.startswith(("E", "W")):
                sev = "MEDIUM"
            else:
                sev = "LOW"

            fix_msg = ""
            fix_data = issue.get("fix")
            if fix_data and isinstance(fix_data, dict):
                fix_msg = fix_data.get("message", "")

            findings.append(Finding(
                file=os.path.relpath(issue["filename"], workspace_dir),
                line=issue.get("location", {}).get("row", 0),
                severity=sev,
                message=f"[{code}] {issue.get('message', '')}",
                tool="ruff",
                rule_id=code,
                suggestion=fix_msg,
            ))

        return ToolResult(
            tool_name="ruff", success=True, findings=findings,
            summary=f"Found {len(findings)} linting issues.",
        )
    except FileNotFoundError:
        return ToolResult(tool_name="ruff", success=False, error="ruff not installed — pip install ruff")
    except Exception as e:
        return ToolResult(tool_name="ruff", success=False, error=str(e))
