import json
import os
import subprocess

from .base import Finding, ToolResult


def run_bandit(workspace_dir: str, changed_files: list) -> ToolResult:
    """Run the bandit security scanner on changed Python files."""
    py_files = [f for f in changed_files if f.endswith(".py")]
    if not py_files:
        return ToolResult(tool_name="bandit", success=True, summary="No Python files to scan.")

    try:
        targets = [
            os.path.join(workspace_dir, f) for f in py_files
            if os.path.exists(os.path.join(workspace_dir, f))
        ]
        if not targets:
            return ToolResult(tool_name="bandit", success=True, summary="Changed files not found in workspace.")

        result = subprocess.run(
            ["bandit", "-f", "json", "-ll", "--"] + targets,
            capture_output=True, text=True, timeout=120,
        )

        data = json.loads(result.stdout or "{}")
        findings = []
        for issue in data.get("results", []):
            cwe = issue.get("issue_cwe", {})
            cwe_id = cwe.get("id", "N/A") if isinstance(cwe, dict) else "N/A"
            findings.append(Finding(
                file=os.path.relpath(issue["filename"], workspace_dir),
                line=issue["line_number"],
                severity=issue.get("issue_severity", "MEDIUM"),
                message=f"{issue['issue_text']} (CWE-{cwe_id})",
                tool="bandit",
                rule_id=issue.get("test_id", ""),
            ))

        return ToolResult(
            tool_name="bandit", success=True, findings=findings,
            summary=f"Scanned {len(targets)} files, found {len(findings)} security issues.",
        )
    except FileNotFoundError:
        return ToolResult(tool_name="bandit", success=False, error="bandit not installed — pip install bandit")
    except Exception as e:
        return ToolResult(tool_name="bandit", success=False, error=str(e))
