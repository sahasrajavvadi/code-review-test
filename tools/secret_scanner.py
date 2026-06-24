import json
import os
import subprocess

from .base import Finding, ToolResult


def run_secret_scan(workspace_dir: str, changed_files: list) -> ToolResult:
    """Run detect-secrets on changed files to find hardcoded credentials."""
    if not changed_files:
        return ToolResult(tool_name="detect-secrets", success=True, summary="No files to scan.")

    try:
        result = subprocess.run(
            ["detect-secrets", "scan", workspace_dir, "--all-files"],
            capture_output=True, text=True, timeout=60,
        )

        data = json.loads(result.stdout or "{}")
        findings = []
        for filepath, secrets in data.get("results", {}).items():
            rel_path = os.path.relpath(filepath, workspace_dir) if os.path.isabs(filepath) else filepath

            if rel_path not in changed_files:
                continue

            for secret in secrets:
                findings.append(Finding(
                    file=rel_path,
                    line=secret.get("line_number", 0),
                    severity="HIGH",
                    message=f"Potential secret detected: {secret.get('type', 'unknown type')}",
                    tool="detect-secrets",
                    rule_id=secret.get("type", ""),
                    suggestion="Move this value to an environment variable or a secrets manager.",
                ))

        return ToolResult(
            tool_name="detect-secrets", success=True, findings=findings,
            summary=f"Found {len(findings)} potential secrets.",
        )
    except FileNotFoundError:
        return ToolResult(
            tool_name="detect-secrets", success=False,
            error="detect-secrets not installed — pip install detect-secrets",
        )
    except Exception as e:
        return ToolResult(tool_name="detect-secrets", success=False, error=str(e))
