"""
write_file tool — Writes content to a file with diff computation and path validation.
"""

from __future__ import annotations

import difflib
import os
import tempfile
from pathlib import Path
from typing import Any

from src.tools.base import BaseTool, RiskLevel, ToolResult
from src.safety.checkpoints import CheckpointManager


class WriteFileTool(BaseTool):
    """Write or create a file with automatic diff computation."""

    def __init__(self, working_dir: str) -> None:
        self._working_dir = Path(working_dir).resolve()

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "Write content to a file. If the file exists, it will be overwritten. "
            "If it doesn't exist, it will be created along with any necessary parent "
            "directories. Always read a file with read_file before modifying it to "
            "understand existing content and avoid data loss. "
            "The path can be relative to the current working directory or absolute."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to write (relative or absolute).",
                },
                "content": {
                    "type": "string",
                    "description": "The complete content to write to the file.",
                },
            },
            "required": ["file_path", "content"],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MODERATE

    def _resolve_path(self, file_path: str) -> Path:
        path = Path(file_path)
        if not path.is_absolute():
            path = self._working_dir / path
        return path.resolve()

    def _validate_path(self, path: Path) -> str | None:
        try:
            path.relative_to(self._working_dir)
        except ValueError:
            return f"Access denied: Path '{path}' is outside the project directory."
        return None

    def _compute_diff(self, old_content: str, new_content: str, file_path: str) -> str:
        """Compute a unified diff between old and new content."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
        return "".join(diff)

    async def execute(self, file_path: str, content: str, **kwargs: Any) -> ToolResult:
        path = self._resolve_path(file_path)

        # Validate path
        error = self._validate_path(path)
        if error:
            return ToolResult(success=False, output=error, display_output=f"🚫 {error}")

        rel_path = path.relative_to(self._working_dir)
        is_new = not path.exists()
        old_content = ""
        diff_text = ""

        if not is_new:
            try:
                old_content = path.read_text(encoding="utf-8")
                diff_text = self._compute_diff(old_content, content, str(rel_path))
            except Exception:
                old_content = ""
                
        # Capture snapshot for safety/undo
        try:
            checkpoint_mgr = CheckpointManager()
            checkpoint_mgr.create_snapshot(str(path), old_content, is_new=is_new)
        except Exception:
            pass

        # Create parent directories
        path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: write to temp file first, then rename
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(path.parent),
                prefix=f".{path.name}.",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp_path, str(path))
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Failed to write file: {e}",
                display_output=f"❌ Write failed: {e}",
            )

        new_lines = len(content.splitlines())
        file_size = len(content.encode("utf-8"))

        if is_new:
            action = "Created new file"
            display = f"✨ Created {rel_path} ({new_lines} lines, {file_size:,} bytes)"
        else:
            old_lines = len(old_content.splitlines())
            delta = new_lines - old_lines
            sign = "+" if delta >= 0 else ""
            action = f"Modified existing file ({sign}{delta} lines)"
            display = f"✏️ Modified {rel_path} ({sign}{delta} lines, now {new_lines} lines)"

        output = f"{action}: {rel_path}\nLines: {new_lines}, Size: {file_size:,} bytes"
        if diff_text:
            output += f"\n\nDiff:\n{diff_text}"

        return ToolResult(
            success=True,
            output=output,
            display_output=display,
            metadata={
                "path": str(rel_path),
                "is_new": is_new,
                "lines": new_lines,
                "size": file_size,
                "diff": diff_text,
            },
        )
