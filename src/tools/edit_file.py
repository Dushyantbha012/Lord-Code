"""
Diff-Based Editing Engine (Feature 3.1)

Provides a smarter alternative to write_file for making targeted edits.
Accepts search/replace blocks, generates unified diffs, and integrates
with the undo system for automatic checkpoints.
"""

import os
import difflib
from typing import List, Dict, Optional

from rich.console import Console
from rich.syntax import Syntax


def edit_file(path: str, edits: list, undo_manager=None) -> str:
    """
    Edit an existing file using search/replace blocks.
    
    Args:
        path: Path to the file to edit.
        edits: List of edit operations. Each is a dict with either:
            - {"search": "old text", "replace": "new text"}  (search/replace mode)
            - {"start_line": int, "end_line": int, "replace": "new content"}  (line-range mode)
        undo_manager: Optional UndoManager instance for automatic checkpointing.
    
    Returns:
        A unified diff showing the changes made, or an error message.
    """
    abs_path = os.path.abspath(path)

    # Validate file exists
    if not os.path.exists(abs_path):
        return f"Error: File '{path}' does not exist. Use write_file to create new files."

    if not os.path.isfile(abs_path):
        return f"Error: '{path}' is not a regular file."

    # Read original content
    try:
        with open(abs_path, "r", errors="replace") as f:
            original_content = f.read()
    except PermissionError:
        return f"Error: Permission denied reading '{path}'."

    # Apply edits
    modified_content = original_content
    applied_count = 0
    errors = []

    for i, edit in enumerate(edits):
        if "search" in edit and "replace" in edit:
            # Search/Replace mode
            search_text = edit["search"]
            replace_text = edit["replace"]

            if search_text not in modified_content:
                # Try to provide helpful context
                errors.append(
                    f"Edit {i + 1}: Search text not found in file. "
                    f"First 80 chars of search: '{search_text[:80]}...'"
                )
                continue

            # Count occurrences
            count = modified_content.count(search_text)
            if count > 1:
                # Replace only the first occurrence to be safe
                modified_content = modified_content.replace(search_text, replace_text, 1)
                errors.append(
                    f"Edit {i + 1}: Warning — found {count} occurrences, replaced only the first."
                )
            else:
                modified_content = modified_content.replace(search_text, replace_text)

            applied_count += 1

        elif "start_line" in edit and "end_line" in edit and "replace" in edit:
            # Line-range mode
            lines = modified_content.splitlines(keepends=True)
            start = edit["start_line"] - 1  # Convert to 0-indexed
            end = edit["end_line"]  # Keep as exclusive upper bound

            if start < 0 or end > len(lines) or start >= end:
                errors.append(
                    f"Edit {i + 1}: Invalid line range {edit['start_line']}-{edit['end_line']} "
                    f"(file has {len(lines)} lines)."
                )
                continue

            replace_text = edit["replace"]
            if not replace_text.endswith("\n") and end < len(lines):
                replace_text += "\n"

            lines[start:end] = [replace_text]
            modified_content = "".join(lines)
            applied_count += 1
        else:
            errors.append(
                f"Edit {i + 1}: Invalid edit format. Expected 'search'/'replace' "
                f"or 'start_line'/'end_line'/'replace'."
            )

    if applied_count == 0:
        error_detail = "\n".join(errors) if errors else "No valid edits provided."
        return f"Error: No edits were applied.\n{error_detail}"

    # Generate unified diff
    diff_text = generate_diff(original_content, modified_content, path)

    # Display the diff with colors
    console = Console()
    console.print("\n[bold cyan]📝 Proposed Changes:[/bold cyan]")
    _display_colored_diff(console, diff_text)

    # Checkpoint before writing (undo system)
    if undo_manager:
        undo_manager.checkpoint(path)

    # Write the modified content
    try:
        with open(abs_path, "w") as f:
            f.write(modified_content)
    except PermissionError:
        return f"Error: Permission denied writing to '{path}'."

    # Record the write in undo system
    if undo_manager:
        undo_manager.record_write(path)

    # Build result
    result_parts = [f"Successfully applied {applied_count} edit(s) to {path}."]
    if errors:
        result_parts.append("Warnings:")
        result_parts.extend(f"  - {e}" for e in errors)
    result_parts.append("\nDiff:")
    result_parts.append(diff_text)

    return "\n".join(result_parts)


def generate_diff(original: str, modified: str, filename: str = "file") -> str:
    """Generate a unified diff between original and modified content."""
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm="",
    )

    return "".join(diff)


def _display_colored_diff(console: Console, diff_text: str) -> None:
    """Display a diff with red/green coloring using Rich."""
    if not diff_text.strip():
        console.print("[dim]  (no differences)[/dim]")
        return

    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            console.print(f"[bold white]{line}[/bold white]")
        elif line.startswith("@@"):
            console.print(f"[cyan]{line}[/cyan]")
        elif line.startswith("+"):
            console.print(f"[green]{line}[/green]")
        elif line.startswith("-"):
            console.print(f"[red]{line}[/red]")
        else:
            console.print(f"[dim]{line}[/dim]")
    console.print()
