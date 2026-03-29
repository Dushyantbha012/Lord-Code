import os
from typing import Any, Dict, List, Optional
from src.tools.base import tool
from src.tools.utils import find_project_root


@tool(
    name="read_file",
    description="Read the contents of a file. Use paths relative to the project root (e.g., 'src/main.py')."
)
def read_file(path: str) -> str:
    """Reads a file relative to the project root. Restricts access to .env files."""
    project_root = find_project_root()
    absolute_path = os.path.abspath(os.path.join(project_root, path))
    
    # Security: Project jail
    if not absolute_path.startswith(project_root):
        return f"Error: Access denied. Cannot read outside project root: {path}"
    
    # Security: .env restriction
    if os.path.basename(absolute_path).startswith(".env"):
        return f"Error: Access denied. Reading .env files is restricted."
    
    if not os.path.exists(absolute_path):
        return f"Error: File not found: {path}"
        
    try:
        with open(absolute_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error: {str(e)}"


@tool(
    name="write_file",
    description="Write or overwrite a file. Use paths relative to the project root."
)
def write_file(path: str, content: str) -> str:
    """Writes content to a file relative to the project root."""
    project_root = find_project_root()
    absolute_path = os.path.abspath(os.path.join(project_root, path))
    
    # Security: Project jail
    if not absolute_path.startswith(project_root):
        return f"Error: Access denied. Cannot write outside project root."
    
    # Security: .env restriction
    if os.path.basename(absolute_path).startswith(".env"):
        return f"Error: Access denied. Modifying .env files is restricted."
        
    try:
        os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
        with open(absolute_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to '{path}'."
    except Exception as e:
        return f"Error: {str(e)}"


@tool(
    name="list_dir",
    description="List the contents of a directory. Defaults to the project root ('.')."
)
def list_dir(path: str = ".") -> str:
    """Lists files and directories relative to the project root."""
    project_root = find_project_root()
    target_path = os.path.abspath(os.path.join(project_root, path))
    
    if not target_path.startswith(project_root):
        return f"Error: Access denied. Cannot list outside project root."
        
    if not os.path.exists(target_path):
        return f"Error: Directory not found: {path}"
        
    if not os.path.isdir(target_path):
        return f"Error: '{path}' is not a directory. Use read_file instead."
        
    try:
        items = os.listdir(target_path)
        # Format for clear LLM consumption
        output = []
        for item in sorted(items):
            item_path = os.path.join(target_path, item)
            prefix = "📁 " if os.path.isdir(item_path) else "📄 "
            output.append(f"{prefix}{item}")
        return "\n".join(output) if output else "(Empty directory)"
    except Exception as e:
        return f"Error: {str(e)}"
