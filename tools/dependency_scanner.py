import json
import os
import subprocess

from .base import Finding, ToolResult


def run_dependency_scan(workspace_dir: str) -> ToolResult:
    """Run pip-audit against requirements.txt to find vulnerable dependencies."""
    req_file = os.path.join(workspace_dir, "requirements.txt")
    if not os.path.exists(req_file):
        return ToolResult(tool_name="pip-audit", success=True, summary="No requirements.txt found.")

    try:
        result = subprocess.run(
            ["pip-audit", "-r", req_file, "-f", "json", "--progress-spinner", "off"],
            capture_output=True, text=True, timeout=120,
        )

        raw = result.stdout or "[]"
        data = json.loads(raw)

        deps = data if isinstance(data, list) else data.get("dependencies", [])
        findings = []
        for dep in deps:
            for vuln in dep.get("vulns", []):
                fix_versions = vuln.get("fix_versions", [])
                fix_msg = f"Upgrade to {', '.join(fix_versions)}" if fix_versions else "No fix available yet"
                desc = vuln.get("description", "")[:200]
                findings.append(Finding(
                    file="requirements.txt",
                    line=0,
                    severity="HIGH",
                    message=f"{dep['name']}=={dep.get('version', '?')}: {vuln.get('id', 'Unknown CVE')} — {desc}",
                    tool="pip-audit",
                    rule_id=vuln.get("id", ""),
                    suggestion=fix_msg,
                ))

        return ToolResult(
            tool_name="pip-audit", success=True, findings=findings,
            summary=f"Scanned dependencies, found {len(findings)} vulnerabilities.",
        )
    except FileNotFoundError:
        return ToolResult(tool_name="pip-audit", success=False, error="pip-audit not installed — pip install pip-audit")
    except Exception as e:
        return ToolResult(tool_name="pip-audit", success=False, error=str(e))
