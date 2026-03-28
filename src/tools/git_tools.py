"""
Git Integration Tools (Feature 3.4)

Provides git operations: commit, branch, diff against ref, stash management, and status.
All commands use subprocess.run with list args (no shell=True) to prevent injection.
"""

import subprocess
from typing import Optional


def _run_git(*args: str, timeout: int = 15) -> str:
    """Run a git command safely and return output."""
    cmd = ["git"] + list(args)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip()
        error = result.stderr.strip()

        if result.returncode != 0:
            return f"Error (exit {result.returncode}): {error or output}"

        return output or "(no output)"

    except FileNotFoundError:
        return "Error: git is not installed or not in PATH."
    except subprocess.TimeoutExpired:
        return f"Error: git command timed out after {timeout}s."


def git_commit(message: str) -> str:
    """
    Stage all changes and create a commit.
    
    Args:
        message: The commit message.
    
    Returns:
        Commit result or error message.
    """
    if not message or not message.strip():
        return "Error: Commit message cannot be empty."

    # Stage all changes
    stage_result = _run_git("add", "-A")
    if stage_result.startswith("Error"):
        return f"Failed to stage changes: {stage_result}"

    # Check if there are staged changes
    status = _run_git("diff", "--cached", "--stat")
    if status == "(no output)" or "Error" in status:
        return "Nothing to commit — no staged changes."

    # Commit
    commit_result = _run_git("commit", "-m", message)
    return commit_result


def git_create_branch(name: str) -> str:
    """
    Create and checkout a new branch.
    
    Args:
        name: Branch name (must be valid git ref name).
    
    Returns:
        Success message or error.
    """
    if not name or not name.strip():
        return "Error: Branch name cannot be empty."

    # Validate branch name characters (basic check)
    import re
    if not re.match(r'^[a-zA-Z0-9._\-/]+$', name):
        return f"Error: Invalid branch name '{name}'. Use only alphanumeric, dots, hyphens, underscores, and forward slashes."

    result = _run_git("checkout", "-b", name)
    return result


def git_diff_ref(ref: str) -> str:
    """
    Show diff against a reference (branch, tag, or commit hash).
    
    Args:
        ref: Git reference to diff against (e.g., 'main', 'HEAD~1', 'v1.0.0').
    
    Returns:
        Diff output or error.
    """
    if not ref or not ref.strip():
        return "Error: Git reference cannot be empty."

    result = _run_git("diff", ref)

    # Truncate large diffs
    if len(result) > 5000:
        result = result[:5000] + "\n\n... (diff truncated — showing first 5000 chars)"

    return result


def git_stash(message: Optional[str] = None) -> str:
    """
    Stash current uncommitted changes.
    
    Args:
        message: Optional stash description.
    
    Returns:
        Stash result or error.
    """
    if message:
        return _run_git("stash", "push", "-m", message)
    else:
        return _run_git("stash", "push")


def git_unstash() -> str:
    """
    Pop the most recent stash entry.
    
    Returns:
        Unstash result or error.
    """
    return _run_git("stash", "pop")


def git_status() -> str:
    """
    Show concise git status.
    
    Returns:
        Short status output or error.
    """
    result = _run_git("status", "--short", "--branch")
    return result
