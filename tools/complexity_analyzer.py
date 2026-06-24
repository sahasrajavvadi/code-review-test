import json
import os
import subprocess

from .base import Finding, ToolResult

COMPLEXITY_THRESHOLD = 10


def run_complexity_analysis(workspace_dir: str, changed_files: list) -> ToolResult:
    """Run radon to measure cyclomatic complexity of changed Python files."""
    py_files = [f for f in changed_files if f.endswith(".py")]
    if not py_files:
        return ToolResult(tool_name="radon", success=True, summary="No Python files to analyze.")

    try:
        targets = [
            os.path.join(workspace_dir, f) for f in py_files
            if os.path.exists(os.path.join(workspace_dir, f))
        ]
        if not targets:
            return ToolResult(tool_name="radon", success=True)

        result = subprocess.run(
            ["radon", "cc", "-j", "-n", "B"] + targets,
            capture_output=True, text=True, timeout=60,
        )

        data = json.loads(result.stdout or "{}")
        findings = []
        for filepath, blocks in data.items():
            rel_path = os.path.relpath(filepath, workspace_dir)
            for block in blocks:
                complexity = block.get("complexity", 0)
                if complexity >= COMPLEXITY_THRESHOLD:
                    sev = "HIGH" if complexity >= 20 else "MEDIUM"
                    name = block.get("name", "?")
                    rank = block.get("rank", "?")
                    findings.append(Finding(
                        file=rel_path,
                        line=block.get("lineno", 0),
                        severity=sev,
                        message=f"'{name}' has cyclomatic complexity {complexity} (rank {rank})",
                        tool="radon",
                        rule_id=f"CC{complexity}",
                        suggestion=f"Break into smaller functions — complexity {complexity} exceeds threshold {COMPLEXITY_THRESHOLD}",
                    ))

        return ToolResult(
            tool_name="radon", success=True, findings=findings,
            summary=f"Found {len(findings)} high-complexity blocks.",
        )
    except FileNotFoundError:
        return ToolResult(tool_name="radon", success=False, error="radon not installed — pip install radon")
    except Exception as e:
        return ToolResult(tool_name="radon", success=False, error=str(e))
