import os

DEFAULT_CONFIG = {
    "agents": {
        "correctness": True,
        "security": True,
        "performance": True,
        "maintainability": True,
        "dependency": True,
        "test": True,
        "autofix": True,
    },
    "severity_threshold": "LOW",
    "ignore": [],
    "pr_size": {
        "max_lines": 500,
        "max_files": 20,
    },
}


def load_config(workspace_dir: str) -> dict:
    """
    Read .ai-reviewer.yml from the repo root. If it doesn't exist, return defaults.

    Example .ai-reviewer.yml:
        agents:
          correctness: true
          security: true
          performance: true
          maintainability: true
          dependency: true
          test: true
          autofix: false           # disable auto-fix suggestions

        severity_threshold: MEDIUM  # only report MEDIUM and above

        ignore:                     # skip these paths
          - "tests/*"
          - "docs/*"
          - "*.md"

        pr_size:
          max_lines: 800            # custom size threshold
          max_files: 30
    """
    for ext in (".yml", ".yaml"):
        config_path = os.path.join(workspace_dir, f".ai-reviewer{ext}")
        if os.path.exists(config_path):
            return _parse_config(config_path)

    return DEFAULT_CONFIG.copy()


def _parse_config(config_path: str) -> dict:
    try:
        import yaml
        with open(config_path, "r") as f:
            user_config = yaml.safe_load(f) or {}

        config = _deep_copy(DEFAULT_CONFIG)
        for key, value in user_config.items():
            if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                config[key].update(value)
            else:
                config[key] = value

        print(f"  📋 Loaded config from {os.path.basename(config_path)}")
        return config
    except ImportError:
        print("  ⚠️ pyyaml not installed — using default config")
        return DEFAULT_CONFIG.copy()
    except Exception as e:
        print(f"  ⚠️ Could not parse {config_path}: {e}")
        return DEFAULT_CONFIG.copy()


def _deep_copy(d: dict) -> dict:
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _deep_copy(v)
        elif isinstance(v, list):
            result[k] = v[:]
        else:
            result[k] = v
    return result


def should_ignore(filename: str, config: dict) -> bool:
    """Check if a file should be skipped based on config ignore patterns."""
    import fnmatch
    for pattern in config.get("ignore", []):
        if fnmatch.fnmatch(filename, pattern):
            return True
    return False


def filter_files(files: list, config: dict) -> list:
    """Filter a file list to remove ignored paths."""
    ignore_patterns = config.get("ignore", [])
    if not ignore_patterns:
        return files
    return [f for f in files if not should_ignore(
        f["filename"] if isinstance(f, dict) else f, config
    )]
