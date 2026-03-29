import subprocess
import os
import shlex
from typing import Any, Dict, List, Optional
from src.tools.base import tool
from src.tools.utils import find_project_root


@tool(
    name="run_command",
    description="Run a shell command in the project root. Be careful with destructive commands."
)
def run_command(command: str) -> str:
    """Executes a shell command. Includes safety checks and execution timeouts."""
    project_root = find_project_root()
    
    # 1. Safety Blacklist (Prevent system-level destruction)
    blacklist = ["rm -rf /", "rm -rf *", "mkfs", "dd if=", "> /dev/"]
    for forbidden in blacklist:
        if forbidden in command:
            return f"Error: Command '{command}' is blacklisted for safety reasons."

    # 2. Deletion Detection (Trigger approval in the agent layer)
    # We return a special prefix if we suspect a deletion, 
    # the agent will then look for 'needs_approval' in its logic.
    deletion_keywords = ["rm ", "rmdir ", "del ", "erase "]
    is_deletion = any(kw in command for kw in deletion_keywords)
    
    # Note: The actual 'approval' happens in the Agent's tool-loop 
    # by checking the tool metadata or a special return prefix.
    # However, since the Tool interface is simple, we'll handle the 
    # 'approval' signal by returning a specific status if the agent 
    # hasn't provided an 'approved' flag (which it won't yet).
    # UPDATED: We'll make the tool return a specific message if approval is needed.
    
    # Check for an override "FORCE_EXECUTE" string the agent might add 
    # after getting user confirmation.
    if is_deletion and not command.startswith("#APPROVED# "):
        return f"APPROVAL_REQUIRED: The command '{command}' performs a deletion. Please confirm execution."

    # Clean the approval prefix if present
    final_command = command.replace("#APPROVED# ", "") if command.startswith("#APPROVED# ") else command

    try:
        # 3. Execution using subprocess
        result = subprocess.run(
            final_command,
            shell=True,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        output = []
        if result.stdout:
            output.append(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            output.append(f"STDERR:\n{result.stderr}")
        if not result.stdout and not result.stderr:
            output.append(f"Command executed with exit code {result.returncode} (No output)")
            
        return "\n".join(output)
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds."
    except Exception as e:
        return f"Error: {str(e)}"
