import os
from pathlib import Path


def find_project_root() -> str:
    """Find the project root by searching upwards for marker files."""
    current = Path(os.getcwd()).resolve()
    # Markers to look for
    markers = [".git", "pyproject.toml", ".env"]

    for parent in [current] + list(current.parents):
        if any((parent / marker).exists() for marker in markers):
            return str(parent)
    
    # Fallback to CWD if no root marker found
    return os.getcwd()
