"""
read_file tool — Reads a file and returns its contents with line numbers.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.tools.base import BaseTool, RiskLevel, ToolResult

# Extensions that are almost certainly binary
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv", ".wav", ".flac",
    ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".o", ".a",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".woff", ".woff2", ".ttf", ".eot",
    ".pyc", ".pyo", ".class",
    ".db", ".sqlite", ".sqlite3",
}

MAX_LINES = 10_000
MAX_FILE_SIZE = 1_024 * 1_024  # 1 MB


class ReadFileTool(BaseTool):
    """Read the contents of a file."""

    def __init__(self, working_dir: str) -> None:
        self._working_dir = Path(working_dir).resolve()

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read the contents of a file at the given path. Returns the file text "
            "content with line numbers. Use this to examine existing code, "
            "configuration files, or any text file before modifying it. "
            "The path can be relative to the current working directory or absolute."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read (relative or absolute).",
                },
            },
            "required": ["file_path"],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    def _resolve_path(self, file_path: str) -> Path:
        """Resolve and validate the file path."""
        path = Path(file_path)
        if not path.is_absolute():
            path = self._working_dir / path
        return path.resolve()

    def _validate_path(self, path: Path) -> str | None:
        """Validate path is within working directory. Returns error message or None."""
        try:
            path.relative_to(self._working_dir)
        except ValueError:
            return f"Access denied: Path '{path}' is outside the project directory."
        return None

    async def execute(self, file_path: str, **kwargs: Any) -> ToolResult:
        path = self._resolve_path(file_path)

        # Validate path
        error = self._validate_path(path)
        if error:
            return ToolResult(success=False, output=error, display_output=f"🚫 {error}")

        # Check existence
        if not path.exists():
            return ToolResult(
                success=False,
                output=f"File not found: {file_path}",
                display_output=f"❌ File not found: {file_path}",
            )

        if not path.is_file():
            return ToolResult(
                success=False,
                output=f"Not a file: {file_path}",
                display_output=f"❌ Not a file: {file_path}",
            )

        # Check for binary
        if path.suffix.lower() in BINARY_EXTENSIONS:
            size = path.stat().st_size
            return ToolResult(
                success=True,
                output=f"[Binary file: {path.suffix} — {size:,} bytes]",
                display_output=f"📦 Binary file: {path.name} ({size:,} bytes)",
                metadata={"binary": True, "size": size},
            )

        # Check file size
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            return ToolResult(
                success=False,
                output=f"File too large: {file_size:,} bytes (max {MAX_FILE_SIZE:,}). Use a more specific approach.",
                display_output=f"⚠️ File too large: {file_size:,} bytes",
            )

        # Read the file
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = path.read_text(encoding="latin-1")
            except Exception:
                return ToolResult(
                    success=True,
                    output=f"[Binary or unreadable file — {file_size:,} bytes]",
                    display_output=f"📦 Binary file: {path.name}",
                )

        lines = content.splitlines()
        total_lines = len(lines)
        truncated = False

        if total_lines > MAX_LINES:
            lines = lines[:MAX_LINES]
            truncated = True

        # Add line numbers
        numbered_lines = [f"{i + 1:>6} | {line}" for i, line in enumerate(lines)]
        numbered_content = "\n".join(numbered_lines)

        if truncated:
            numbered_content += f"\n\n[TRUNCATED — showing first {MAX_LINES:,} of {total_lines:,} lines]"

        # Detect language from extension
        lang_map = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".jsx": "JSX", ".tsx": "TSX", ".html": "HTML", ".css": "CSS",
            ".json": "JSON", ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
            ".md": "Markdown", ".rs": "Rust", ".go": "Go", ".java": "Java",
            ".rb": "Ruby", ".sh": "Shell", ".bash": "Bash",
            ".sql": "SQL", ".xml": "XML", ".c": "C", ".cpp": "C++",
            ".h": "C Header", ".hpp": "C++ Header",
        }
        language = lang_map.get(path.suffix.lower(), "Unknown")

        rel_path = path.relative_to(self._working_dir)

        return ToolResult(
            success=True,
            output=f"File: {rel_path} ({total_lines} lines, {file_size:,} bytes, {language})\n\n{numbered_content}",
            display_output=f"📄 Read {rel_path} ({total_lines} lines, {file_size:,} bytes)",
            metadata={
                "path": str(rel_path),
                "lines": total_lines,
                "size": file_size,
                "language": language,
                "truncated": truncated,
            },
        )
