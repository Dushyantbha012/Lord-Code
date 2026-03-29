"""
Checkpoint Manager — Handles file snapshots for safe undo operations.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


class CheckpointManager:
    """Manages file checkpoints for the /undo command."""

    def __init__(self, max_history: int = 10) -> None:
        self.max_history = max_history
        self._history_file = Path.home() / ".lord-code" / "checkpoints" / "undo_stack.json"
        self._history_file.parent.mkdir(parents=True, exist_ok=True)
        self._stack: list[dict] = self._load_stack()

    def _load_stack(self) -> list[dict]:
        if self._history_file.exists():
            try:
                return json.loads(self._history_file.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save_stack(self) -> None:
        try:
            self._history_file.write_text(json.dumps(self._stack, indent=2), encoding="utf-8")
        except Exception:
            pass

    def create_snapshot(self, file_path: str, content: str, is_new: bool = False) -> None:
        """
        Create a snapshot of a file before modifying it.
        If is_new is True, content is ignored and undo will delete the file.
        """
        abs_path = str(Path(file_path).resolve())
        snapshot = {
            "path": abs_path,
            "content": content,
            "is_new": is_new,
            "timestamp": time.time(),
        }
        self._stack.append(snapshot)
        
        # Enforce max history size
        if len(self._stack) > self.max_history:
            self._stack.pop(0)
            
        self._save_stack()

    def revert_last(self) -> tuple[bool, str]:
        """
        Revert the most recent file modification.
        Returns (success, message).
        """
        if not self._stack:
            return False, "No operations to undo."

        last_action = self._stack.pop()
        self._save_stack()

        path_str = last_action["path"]
        path = Path(path_str)
        is_new = last_action.get("is_new", False)

        try:
            if is_new:
                # The file was created by the tool, so undoing means deleting it.
                if path.exists():
                    path.unlink()
                return True, f"Deleted newly created file: {path_str}"
            else:
                # The file existed before, restore old content.
                content = last_action.get("content", "")
                if not path.parent.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                return True, f"Reverted file: {path_str}"
        except Exception as e:
            return False, f"Failed to undo {path_str}: {e}"
