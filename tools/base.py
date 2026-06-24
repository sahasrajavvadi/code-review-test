from dataclasses import dataclass, field


@dataclass
class Finding:
    file: str
    line: int
    severity: str
    message: str
    tool: str
    rule_id: str = ""
    suggestion: str = ""


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    findings: list = field(default_factory=list)
    summary: str = ""
    error: str = ""

    def to_prompt_text(self) -> str:
        if not self.success:
            return f"[{self.tool_name}] Not available: {self.error}"
        if not self.findings:
            return f"[{self.tool_name}] No issues found."
        lines = [f"[{self.tool_name}] {len(self.findings)} issue(s):"]
        for f in self.findings:
            lines.append(f"  - [{f.severity}] {f.file}:{f.line} — {f.message}")
            if f.suggestion:
                lines.append(f"    Suggested fix: {f.suggestion}")
        return "\n".join(lines)
