import os
import shutil
import subprocess
import tempfile


class PRWorkspace:
    """Clones a repo at the PR's head commit into a temp directory for tool analysis."""

    def __init__(self, repo_name: str, pr_number: int):
        self.repo_name = repo_name
        self.pr_number = pr_number
        self.workspace_dir = None

    def setup(self) -> str:
        self.workspace_dir = tempfile.mkdtemp(prefix="ai-reviewer-")
        token = os.getenv("GITHUB_TOKEN")
        clone_url = f"https://x-access-token:{token}@github.com/{self.repo_name}.git"

        subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", clone_url, self.workspace_dir],
            capture_output=True, text=True, timeout=120,
        )
        subprocess.run(
            ["git", "-C", self.workspace_dir, "fetch", "origin",
             f"pull/{self.pr_number}/head", "--depth", "1", "--quiet"],
            capture_output=True, text=True, timeout=120,
        )
        subprocess.run(
            ["git", "-C", self.workspace_dir, "checkout", "FETCH_HEAD", "--quiet"],
            capture_output=True, text=True, timeout=30,
        )
        return self.workspace_dir

    def cleanup(self):
        if self.workspace_dir and os.path.exists(self.workspace_dir):
            shutil.rmtree(self.workspace_dir, ignore_errors=True)

    def __enter__(self):
        return self.setup()

    def __exit__(self, *args):
        self.cleanup()
