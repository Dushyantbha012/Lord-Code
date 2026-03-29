import subprocess
import os
import glob

from src.tools.search import (
    find_files,
    search_in_files,
    find_definition,
    get_git_diff,
    get_git_log,
)
from src.tools.edit_file import edit_file as _edit_file_impl
from src.tools.git_tools import (
    git_commit,
    git_create_branch,
    git_diff_ref,
    git_stash,
    git_unstash,
    git_status,
)
from src.tools.test_runner import run_tests


# ── Module-level reference to undo manager (set by ChatLoop) ──
_undo_manager = None


def set_undo_manager(manager):
    """Called by ChatLoop to inject the UndoManager instance."""
    global _undo_manager
    _undo_manager = manager


# ── Module-level reference to plan manager (set by ChatLoop) ──
_plan_manager = None


def set_plan_manager(manager):
    """Called by ChatLoop to inject the PlanManager instance."""
    global _plan_manager
    _plan_manager = manager


def read_file(path: str) -> str:
    try:
        with open(path, 'r') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_file(path: str, content: str) -> str:
    try:
        # Checkpoint before writing (undo system)
        if _undo_manager:
            _undo_manager.checkpoint(path)

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)

        # Record the write in undo system
        if _undo_manager:
            _undo_manager.record_write(path)

        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

def edit_file(path: str, edits: list) -> str:
    """Wrapper that passes the undo_manager to the edit engine."""
    return _edit_file_impl(path, edits, undo_manager=_undo_manager)

def execute_command(command: str) -> str:
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = result.stdout if result.stdout else ""
        error = result.stderr if result.stderr else ""
        return f"STDOUT:\n{output}\nSTDERR:\n{error}\nExit Code: {result.returncode}"
    except Exception as e:
        return f"Error executing command: {str(e)}"

def list_files(path: str) -> str:
    try:
        files = os.listdir(path)
        return "\n".join(files)
    except Exception as e:
        return f"Error listing files: {str(e)}"

def grep_search(pattern: str, path: str) -> str:
    try:
        # Use simple recursive search if it's a directory, else search file
        if os.path.isdir(path):
            cmd = f"grep -rE \"{pattern}\" \"{path}\""
        else:
            cmd = f"grep -E \"{pattern}\" \"{path}\""
        return execute_command(cmd)
    except Exception as e:
        return f"Error in grep search: {str(e)}"


# ── Multi-Step Planning Handlers (Feature 4) ──

def create_plan(title: str, steps: list) -> str:
    """Create a structured multi-step plan."""
    if not _plan_manager:
        return "Error: Plan manager not initialized."
    try:
        plan = _plan_manager.create_plan(title, steps)
        return _plan_manager.to_llm_context()
    except Exception as e:
        return f"Error creating plan: {str(e)}"


def update_plan(action: str, step_index: int = None, description: str = None) -> str:
    """Modify the current plan mid-execution."""
    if not _plan_manager:
        return "Error: Plan manager not initialized."
    if not _plan_manager.current_plan:
        return "Error: No active plan to update."

    try:
        if action == "add_step":
            if not description:
                return "Error: 'description' is required for 'add_step'."
            return _plan_manager.add_step(description, at_index=step_index)
        elif action == "remove_step":
            if step_index is None:
                return "Error: 'step_index' is required for 'remove_step'."
            return _plan_manager.remove_step(step_index)
        elif action == "modify_step":
            if step_index is None or not description:
                return "Error: 'step_index' and 'description' are required for 'modify_step'."
            return _plan_manager.modify_step(step_index, description)
        else:
            return f"Error: Unknown action '{action}'. Use 'add_step', 'remove_step', or 'modify_step'."
    except Exception as e:
        return f"Error updating plan: {str(e)}"


# Registry for easy dispatch
TOOL_HANDLERS = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "execute_command": execute_command,
    "list_files": list_files,
    "grep_search": grep_search,
    # Smart Search Tools (Feature 2.2)
    "find_files": find_files,
    "search_in_files": search_in_files,
    "find_definition": find_definition,
    # Git Tools (Features 2.2 + 3.4)
    "get_git_diff": get_git_diff,
    "get_git_log": get_git_log,
    "git_commit": git_commit,
    "git_create_branch": git_create_branch,
    "git_diff_ref": git_diff_ref,
    "git_stash": git_stash,
    "git_unstash": git_unstash,
    "git_status": git_status,
    # Test Execution (Feature 3.3)
    "run_tests": run_tests,
    # Multi-Step Planning (Feature 4)
    "create_plan": create_plan,
    "update_plan": update_plan,
}

