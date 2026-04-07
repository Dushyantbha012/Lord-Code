import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from src.tools.utils import find_project_root

class ContextManager:
    """Manages hierarchical context retrieval for the Lord-Code Agent."""

    def __init__(self):
        self.project_root = Path(find_project_root())
        self.memory_path = self.project_root / ".lord_code" / "memory.json"
        self._ensure_memory_file()

    def _ensure_memory_file(self):
        """Ensure the memory.json file exists."""
        if not self.memory_path.parent.exists():
            self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.memory_path.exists():
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def get_global_context(self) -> str:
        """Reads project-wide context from lord_code.md."""
        global_path = self.project_root / "lord_code.md"
        if global_path.exists():
            try:
                with open(global_path, "r", encoding="utf-8") as f:
                    return f"\n[GLOBAL CONTEXT]\n{f.read()}\n"
            except Exception:
                pass
        return ""

    def get_local_context(self, current_dir: Optional[str] = None) -> str:
        """Reads local context from .context.md files by walking up from current_dir."""
        if not current_dir:
            current_dir = os.getcwd()
            
        current_path = Path(current_dir).resolve()
        local_contexts = []
        
        # Walk up to the project root
        temp_path = current_path
        while temp_path.exists() and temp_path.parts[:len(self.project_root.parts)] == self.project_root.parts:
            context_file = temp_path / ".context.md"
            if context_file.exists():
                try:
                    with open(context_file, "r", encoding="utf-8") as f:
                        local_contexts.append(f"Context from {temp_path.relative_to(self.project_root)}:\n{f.read()}")
                except Exception:
                    pass
            if temp_path == self.project_root:
                break
            temp_path = temp_path.parent

        if local_contexts:
            return "\n[LOCAL CONTEXT]\n" + "\n---\n".join(reversed(local_contexts)) + "\n"
        return ""

    def get_memory_context(self) -> str:
        """Reads learned facts from memory.json."""
        if self.memory_path.exists():
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    memory = json.load(f)
                    if memory:
                        memory_str = "\n".join([f"- {k}: {v}" for k, v in memory.items()])
                        return f"\n[LEARNED MEMORY]\n{memory_str}\n"
            except Exception:
                pass
        return ""

    def get_full_context_block(self, current_dir: Optional[str] = None) -> str:
        """Combines all context layers into a single formatted block."""
        global_ctx = self.get_global_context()
        local_ctx = self.get_local_context(current_dir)
        memory_ctx = self.get_memory_context()
        
        if not (global_ctx or local_ctx or memory_ctx):
            return ""
            
        return (
            "\n<context>\n"
            "This is your current project context. Follow these rules and memory facts strictly:\n"
            f"{global_ctx}{local_ctx}{memory_ctx}"
            "</context>\n"
        )
