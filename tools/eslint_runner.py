import json
import os
import subprocess

from .base import Finding, ToolResult


def run_eslint(workspace_dir: str, changed_files: list) -> ToolResult:
    """Run ESLint on changed JS/TS files for multi-language support."""
    js_extensions = (".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs")
    js_files = [f for f in changed_files if any(f.endswith(ext) for ext in js_extensions)]

    if not js_files:
        return ToolResult(tool_name="eslint", success=True, summary="No JS/TS files to lint.")

    try:
        targets = [
            os.path.join(workspace_dir, f) for f in js_files
            if os.path.exists(os.path.join(workspace_dir, f))
        ]
        if not targets:
            return ToolResult(tool_name="eslint", success=True)

        # Check if project has its own eslint config — use it if so
        has_config = any(
            os.path.exists(os.path.join(workspace_dir, cfg))
            for cfg in [".eslintrc.js", ".eslintrc.json", ".eslintrc.yml",
                        ".eslintrc.yaml", ".eslintrc", "eslint.config.js",
                        "eslint.config.mjs", "eslint.config.cjs"]
        )

        cmd = ["eslint", "--format", "json"]
        if not has_config:
            cmd.extend(["--no-eslintrc", "--env", "es2021", "--env", "node",
                         "--parser-options", "ecmaVersion:2021",
                         "--rule", '{"no-unused-vars":"warn","no-undef":"error",'
                                   '"eqeqeq":"error","no-eval":"error",'
                                   '"no-implied-eval":"error"}'])
        cmd.extend(targets)

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, cwd=workspace_dir,
        )

        raw = result.stdout or "[]"
        data = json.loads(raw)

        findings = []
        for file_result in data:
            filepath = file_result.get("filePath", "")
            rel_path = (
                os.path.relpath(filepath, workspace_dir)
                if os.path.isabs(filepath) else filepath
            )

            for msg in file_result.get("messages", []):
                sev = "HIGH" if msg.get("severity", 1) >= 2 else "MEDIUM"
                rule = msg.get("ruleId", "unknown")
                findings.append(Finding(
                    file=rel_path,
                    line=msg.get("line", 0),
                    severity=sev,
                    message=f"[{rule}] {msg.get('message', '')}",
                    tool="eslint",
                    rule_id=rule,
                    suggestion=msg.get("fix", {}).get("text", "") if msg.get("fix") else "",
                ))

        return ToolResult(
            tool_name="eslint", success=True, findings=findings,
            summary=f"Found {len(findings)} JS/TS issues.",
        )
    except FileNotFoundError:
        return ToolResult(
            tool_name="eslint", success=False,
            error="eslint not installed — npm install -g eslint",
        )
    except Exception as e:
        return ToolResult(tool_name="eslint", success=False, error=str(e))
