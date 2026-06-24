import re


def detect_breaking_changes(files: list) -> dict:
    """
    Parse PR file patches to detect removed/renamed public APIs.
    Catches: removed functions, removed classes, removed API endpoints,
    removed JS/TS exports, changed function signatures.
    """
    removed_functions = []
    removed_classes = []
    removed_endpoints = []
    changed_signatures = []

    for file_info in files:
        patch = file_info.get("patch", "")
        filename = file_info.get("filename", "")
        if not patch:
            continue

        removed_defs = {}
        added_defs = {}

        for line in patch.split("\n"):
            stripped = line.strip()

            if line.startswith("-") and not line.startswith("---"):
                code = stripped.lstrip("-").strip()
                _extract_definitions(code, filename, removed_defs,
                                     removed_functions, removed_classes, removed_endpoints)

            elif line.startswith("+") and not line.startswith("+++"):
                code = stripped.lstrip("+").strip()
                _extract_definitions(code, filename, added_defs, [], [], [])

        for name, sig in removed_defs.items():
            if name in added_defs and added_defs[name] != sig:
                changed_signatures.append({
                    "name": name,
                    "file": filename,
                    "old": sig,
                    "new": added_defs[name],
                })

    findings = []
    for func in removed_functions:
        if not any(s["name"] == func["name"] for s in changed_signatures):
            findings.append(
                f"Public function `{func['name']}` removed from `{func['file']}` — "
                "existing callers will break"
            )
    for cls in removed_classes:
        findings.append(
            f"Class `{cls['name']}` removed from `{cls['file']}` — "
            "any code importing it will break"
        )
    for ep in removed_endpoints:
        findings.append(
            f"API endpoint `{ep['method']} {ep['path']}` removed from `{ep['file']}` — "
            "clients will get 404s"
        )
    for sig in changed_signatures:
        findings.append(
            f"Function signature changed in `{sig['file']}`: "
            f"`{sig['old']}` → `{sig['new']}` — existing callers may break"
        )

    return {
        "has_breaking_changes": len(findings) > 0,
        "findings": findings,
        "removed_functions": removed_functions,
        "removed_classes": removed_classes,
        "removed_endpoints": removed_endpoints,
        "changed_signatures": changed_signatures,
    }


def _extract_definitions(code, filename, defs_dict, funcs_list, classes_list, endpoints_list):
    """Extract function/class/endpoint definitions from a line of code."""
    # Python functions
    m = re.match(r"def\s+(\w+)\s*\(([^)]*)\)", code)
    if m and not m.group(1).startswith("_"):
        name = m.group(1)
        sig = f"def {name}({m.group(2)})"
        defs_dict[name] = sig
        funcs_list.append({"name": name, "file": filename})
        return

    # Python classes
    m = re.match(r"class\s+(\w+)", code)
    if m:
        classes_list.append({"name": m.group(1), "file": filename})
        return

    # JS/TS exports
    m = re.match(r"export\s+(?:default\s+)?(?:function|const|class|let|var)\s+(\w+)", code)
    if m:
        funcs_list.append({"name": m.group(1), "file": filename})
        return

    # API endpoints — Flask/FastAPI decorators
    m = re.search(r"@\w+\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)", code)
    if m:
        endpoints_list.append({"method": m.group(1).upper(), "path": m.group(2), "file": filename})
        return

    # Express.js routes
    m = re.search(r"\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)", code)
    if m:
        endpoints_list.append({"method": m.group(1).upper(), "path": m.group(2), "file": filename})
