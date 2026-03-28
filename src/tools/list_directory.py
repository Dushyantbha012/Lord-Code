"""
list_directory tool — Lists directory contents respecting .gitignore.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.tools.base import BaseTool, RiskLevel, ToolResult

try:
    import pathspec
    HAS_PATHSPEC = True
except ImportError:
    HAS_PATHSPEC = False

MAX_ENTRIES = 300
MAX_DEPTH = 5


def _format_size(size: int) -> str:
    """Format file size in human-readable form."""
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f}MB"
    return f"{size / (1024 * 1024 * 1024):.1f}GB"


def _load_gitignore(directory: Path) -> pathspec.PathSpec | None:
    """Load .gitignore patterns from a directory."""
    if not HAS_PATHSPEC:
        return None
    gitignore = directory / ".gitignore"
    if not gitignore.exists():
        return None
    try:
        patterns = gitignore.read_text().splitlines()
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    except Exception:
        return None


class ListDirectoryTool(BaseTool):
    """List files and directories."""

    def __init__(self, working_dir: str) -> None:
        self._working_dir = Path(working_dir).resolve()

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return (
            "List the files and directories at the given path. Shows file sizes "
            "and respects .gitignore patterns. Use this to explore or understand "
            "the structure of a project. Defaults to the project root if no path "
            "is provided."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list (default: project root).",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "If true, list recursively as a tree. Default false.",
                },
            },
            "required": [],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.SAFE

    def _resolve_path(self, dir_path: str) -> Path:
        path = Path(dir_path)
        if not path.is_absolute():
            path = self._working_dir / path
        return path.resolve()

    def _build_tree(
        self,
        directory: Path,
        gitignore: pathspec.PathSpec | None,
        prefix: str = "",
        depth: int = 0,
        count: list | None = None,
    ) -> list[str]:
        """Build a tree representation of the directory."""
        if count is None:
            count = [0]

        if depth > MAX_DEPTH or count[0] > MAX_ENTRIES:
            return [f"{prefix}... (depth/entry limit reached)"]

        lines: list[str] = []

        try:
            entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return [f"{prefix}[Permission Denied]"]

        # Filter entries
        filtered = []
        for entry in entries:
            # Skip hidden files/dirs (except .gitignore itself)
            if entry.name.startswith(".") and entry.name not in (".gitignore",):
                continue

            # Check gitignore
            if gitignore:
                try:
                    rel = entry.relative_to(self._working_dir)
                    check_path = str(rel) + ("/" if entry.is_dir() else "")
                    if gitignore.match_file(check_path):
                        continue
                except ValueError:
                    pass

            filtered.append(entry)

        for i, entry in enumerate(filtered):
            count[0] += 1
            if count[0] > MAX_ENTRIES:
                lines.append(f"{prefix}... ({MAX_ENTRIES} entry limit reached)")
                break

            is_last = i == len(filtered) - 1
            connector = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")

            if entry.is_dir():
                lines.append(f"{prefix}{connector}📁 {entry.name}/")
                sub = self._build_tree(entry, gitignore, child_prefix, depth + 1, count)
                lines.extend(sub)
            else:
                size = _format_size(entry.stat().st_size)
                lines.append(f"{prefix}{connector}📄 {entry.name} ({size})")

        return lines

    def _list_flat(
        self,
        directory: Path,
        gitignore: pathspec.PathSpec | None,
    ) -> list[str]:
        """Flat (non-recursive) directory listing."""
        lines: list[str] = []

        try:
            entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return ["[Permission Denied]"]

        for entry in entries:
            if entry.name.startswith(".") and entry.name not in (".gitignore",):
                continue

            if gitignore:
                try:
                    rel = entry.relative_to(self._working_dir)
                    check_path = str(rel) + ("/" if entry.is_dir() else "")
                    if gitignore.match_file(check_path):
                        continue
                except ValueError:
                    pass

            if entry.is_dir():
                lines.append(f"  📁 {entry.name}/")
            else:
                size = _format_size(entry.stat().st_size)
                lines.append(f"  📄 {entry.name} ({size})")

        return lines

    async def execute(
        self,
        path: str = ".",
        recursive: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        dir_path = self._resolve_path(path)

        # Validate
        try:
            dir_path.relative_to(self._working_dir)
        except ValueError:
            return ToolResult(
                success=False,
                output=f"Access denied: Path is outside the project directory.",
                display_output="🚫 Path outside project directory",
            )

        if not dir_path.exists():
            return ToolResult(
                success=False,
                output=f"Directory not found: {path}",
                display_output=f"❌ Directory not found: {path}",
            )

        if not dir_path.is_dir():
            return ToolResult(
                success=False,
                output=f"Not a directory: {path}",
                display_output=f"❌ Not a directory: {path}",
            )

        # Load gitignore from project root
        gitignore = _load_gitignore(self._working_dir)

        rel_path = dir_path.relative_to(self._working_dir)
        display_path = str(rel_path) if str(rel_path) != "." else "project root"

        if recursive:
            tree_lines = self._build_tree(dir_path, gitignore)
            header = f"📁 {display_path}/"
            content = header + "\n" + "\n".join(tree_lines)
        else:
            flat_lines = self._list_flat(dir_path, gitignore)
            header = f"📁 {display_path}/ ({len(flat_lines)} items)"
            content = header + "\n" + "\n".join(flat_lines)

        return ToolResult(
            success=True,
            output=content,
            display_output=f"📁 Listed {display_path}/",
            metadata={"path": str(rel_path)},
        )
