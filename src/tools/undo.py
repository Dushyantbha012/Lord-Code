"""
Undo/Rollback System (Feature 3.5)

Provides automatic checkpoints before file modifications and supports
reverting the last set of changes. Undo history is session-scoped (in-memory only).
"""

import os
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class FileSnapshot:
    """A snapshot of a single file's content before modification."""
    path: str
    old_content: Optional[str]  # None if file didn't exist
    new_content: Optional[str] = None  # Filled after modification


@dataclass
class ChangeSet:
    """A group of file changes made in a single AI turn."""
    timestamp: float
    description: str
    files: List[FileSnapshot] = field(default_factory=list)

    @property
    def summary(self) -> str:
        ts = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        file_list = ", ".join(os.path.basename(f.path) for f in self.files)
        return f"[{ts}] {self.description} — {len(self.files)} file(s): {file_list}"


class UndoManager:
    """
    Manages automatic checkpoints and undo operations.
    
    Session-scoped: history lives in memory and is lost when the session ends.
    Changes are grouped by "turn" — all file edits in one AI response form one ChangeSet.
    """

    MAX_HISTORY = 50

    def __init__(self, working_dir: str):
        self.working_dir = working_dir
        self.change_log: List[ChangeSet] = []
        self._current_turn: Optional[ChangeSet] = None

    def begin_turn(self, description: str = "AI edit") -> None:
        """Start a new change set for this AI turn."""
        self._current_turn = ChangeSet(
            timestamp=time.time(),
            description=description,
        )

    def checkpoint(self, file_path: str) -> None:
        """
        Snapshot a file's current content before modification.
        Must be called BEFORE the file is written to.
        """
        abs_path = self._resolve(file_path)

        # Read existing content (None if file doesn't exist yet)
        old_content = None
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r", errors="replace") as f:
                    old_content = f.read()
            except (PermissionError, IsADirectoryError):
                return  # Can't checkpoint this file

        snapshot = FileSnapshot(path=abs_path, old_content=old_content)

        # If no turn is active, create an implicit one
        if self._current_turn is None:
            self.begin_turn("File modification")

        self._current_turn.files.append(snapshot)

    def record_write(self, file_path: str) -> None:
        """
        Record the new content of a file after modification.
        Must be called AFTER the file is written to.
        """
        abs_path = self._resolve(file_path)

        if self._current_turn is None:
            return

        # Find the matching snapshot and fill in new_content
        for snapshot in reversed(self._current_turn.files):
            if snapshot.path == abs_path and snapshot.new_content is None:
                try:
                    with open(abs_path, "r", errors="replace") as f:
                        snapshot.new_content = f.read()
                except (PermissionError, IsADirectoryError):
                    pass
                break

    def end_turn(self) -> None:
        """Finalize the current change set and add it to the log."""
        if self._current_turn and self._current_turn.files:
            self.change_log.append(self._current_turn)
            # Enforce max history
            if len(self.change_log) > self.MAX_HISTORY:
                self.change_log = self.change_log[-self.MAX_HISTORY:]
        self._current_turn = None

    def undo_last(self) -> str:
        """
        Revert the most recent change set.
        Returns a human-readable summary of what was reverted.
        """
        if not self.change_log:
            return "Nothing to undo — no changes recorded in this session."

        changeset = self.change_log.pop()
        reverted = []
        errors = []

        for snapshot in reversed(changeset.files):
            try:
                if snapshot.old_content is None:
                    # File was newly created — delete it
                    if os.path.exists(snapshot.path):
                        os.remove(snapshot.path)
                        reverted.append(f"  🗑  Deleted {os.path.relpath(snapshot.path, self.working_dir)}")
                else:
                    # Restore original content
                    os.makedirs(os.path.dirname(snapshot.path), exist_ok=True)
                    with open(snapshot.path, "w") as f:
                        f.write(snapshot.old_content)
                    reverted.append(f"  ↩  Restored {os.path.relpath(snapshot.path, self.working_dir)}")
            except Exception as e:
                errors.append(f"  ❌ Failed to revert {snapshot.path}: {e}")

        parts = [f"Reverted: {changeset.description}"]
        parts.extend(reverted)
        if errors:
            parts.extend(errors)
        return "\n".join(parts)

    def get_change_log(self) -> str:
        """Return a formatted change log for this session."""
        if not self.change_log:
            return "No changes recorded in this session."

        lines = [f"Session Change Log ({len(self.change_log)} change set(s)):"]
        for i, cs in enumerate(reversed(self.change_log), 1):
            lines.append(f"  {i}. {cs.summary}")
        return "\n".join(lines)

    def _resolve(self, file_path: str) -> str:
        """Resolve a path relative to working directory."""
        if os.path.isabs(file_path):
            return os.path.abspath(file_path)
        return os.path.abspath(os.path.join(self.working_dir, file_path))
