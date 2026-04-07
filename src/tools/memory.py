import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from src.tools.base import tool
from src.tools.utils import find_project_root

def _load_memory() -> Dict[str, Any]:
    """Internal helper to load memory from .lord_code/memory.json."""
    project_root = Path(find_project_root())
    memory_path = project_root / ".lord_code" / "memory.json"
    
    if not memory_path.exists():
        return {}
        
    try:
        with open(memory_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_memory(memory: Dict[str, Any]):
    """Internal helper to save memory to .lord_code/memory.json."""
    project_root = Path(find_project_root())
    memory_path = project_root / ".lord_code" / "memory.json"
    
    if not memory_path.parent.exists():
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        
    try:
        with open(memory_path, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=4)
    except Exception:
        pass

@tool(
    name="remember",
    description="Store a key-value fact in the agent's persistent memory. Use this for project-specific details or user preferences."
)
def remember(key: str, value: str) -> str:
    """Stores a fact in the local memory file."""
    memory = _load_memory()
    memory[key] = value
    _save_memory(memory)
    return f"I have remembered: {key} -> {value}"

@tool(
    name="recall",
    description="Look up a stored fact from the agent's persistent memory using a key."
)
def recall(key: str) -> str:
    """Recalls a fact from the local memory file."""
    memory = _load_memory()
    if key in memory:
        return f"Fact for '{key}': {memory[key]}"
    return f"I don't remember any fact for '{key}'."
