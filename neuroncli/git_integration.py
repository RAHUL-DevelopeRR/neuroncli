"""NeuronCLI — Git integration. Auto-commit AI edits like Aider."""

from __future__ import annotations

import subprocess
from pathlib import Path


def is_git_repo(working_dir: str) -> bool:
    """Check if the working directory is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=working_dir, capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def git_auto_commit(working_dir: str, files: list[str], message: str) -> str | None:
    """Stage specific files and commit with a descriptive message.
    Returns commit hash on success, None on failure.
    """
    if not is_git_repo(working_dir):
        return None

    try:
        # Stage only the modified files
        for f in files:
            subprocess.run(
                ["git", "add", str(f)],
                cwd=working_dir, capture_output=True, timeout=5,
            )

        # Check if there are staged changes
        status = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=working_dir, capture_output=True, timeout=5,
        )
        if status.returncode == 0:
            return None  # Nothing staged

        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", f"neuron: {message}"],
            cwd=working_dir, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            # Extract short hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=working_dir, capture_output=True, text=True, timeout=5,
            )
            return hash_result.stdout.strip() if hash_result.returncode == 0 else "ok"
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def git_status(working_dir: str) -> str:
    """Get git status summary."""
    if not is_git_repo(working_dir):
        return "Not a git repository."
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=working_dir, capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or "Working tree clean."
    except Exception:
        return "Error running git status."


def git_diff(working_dir: str) -> str:
    """Get current unstaged diff."""
    if not is_git_repo(working_dir):
        return "Not a git repository."
    try:
        result = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=working_dir, capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or "No changes."
    except Exception:
        return "Error running git diff."
