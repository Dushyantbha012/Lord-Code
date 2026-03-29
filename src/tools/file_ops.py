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
def list_dir(path: str = ".", recursive: bool = False, max_depth: int = 3) -> str:
    """Lists files and directories relative to the project root. Supports recursion and filtering."""
    project_root = find_project_root()
    target_path = os.path.abspath(os.path.join(project_root, path))
    
    if not target_path.startswith(project_root):
        return f"Error: Access denied. Cannot list outside project root."
        
    if not os.path.exists(target_path):
        return f"Error: Directory not found: {path}"
        
    if not os.path.isdir(target_path):
        return f"Error: '{path}' is not a directory. Use read_file instead."
        
    # Directories to ignore
    ignore_dirs = {".git", "venv", ".venv", "__pycache__", "node_modules"}
    
    output = []
    
    def walk(current_path, current_rel_path, depth):
        if depth > max_depth:
            return
            
        try:
            items = sorted(os.listdir(current_path))
            for i, item in enumerate(items):
                if item in ignore_dirs:
                    continue
                    
                item_path = os.path.join(current_path, item)
                item_rel_path = os.path.join(current_rel_path, item) if current_rel_path != "." else item
                is_dir = os.path.isdir(item_path)
                
                # Visual rendering
                indent = "  " * depth
                connector = "└── " if i == len(items) - 1 else "├── "
                prefix = "📁 " if is_dir else "📄 "
                output.append(f"{indent}{connector}{prefix}{item}")
                
                if is_dir and recursive:
                    walk(item_path, item_rel_path, depth + 1)
        except Exception as e:
            output.append(f"{'  ' * depth}└── [Error: {str(e)}]")

    output.append(f"Project Root: {os.path.basename(project_root)}/{path if path != '.' else ''}")
    walk(target_path, path, 0)
    
    return "\n".join(output) if len(output) > 1 else "(Empty directory or contains only ignored items)"
