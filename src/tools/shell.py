import subprocess
import os
import shlex
from typing import Any, Dict, List, Optional
from src.tools.base import tool
from src.tools.utils import find_project_root


@tool(
    name="run_command",
    description="Run a shell command in the project root."
)
def run_command(command: str) -> str:
    """Executes a shell command in the project root."""
    project_root = find_project_root()
    
    try:
        # Execution using subprocess
        result = subprocess.run(
            command,
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
