"""
System Prompt Builder — Dynamic system prompt with project context.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path


# ---------------------------------------------------------------------------
# Project type detection
# ---------------------------------------------------------------------------

PROJECT_INDICATORS = {
    "package.json": "Node.js",
    "pyproject.toml": "Python",
    "setup.py": "Python",
    "requirements.txt": "Python",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java (Gradle)",
    "Gemfile": "Ruby",
    "composer.json": "PHP",
    "docker-compose.yml": "Docker",
    "Dockerfile": "Docker",
    "Makefile": "Make",
    ".flutter": "Flutter/Dart",
    "pubspec.yaml": "Flutter/Dart",
}


def _detect_project_type(working_dir: Path) -> str:
    """Detect the project type from config files."""
    detected = []
    for filename, project_type in PROJECT_INDICATORS.items():
        if (working_dir / filename).exists():
            if project_type not in detected:
                detected.append(project_type)
    return ", ".join(detected) if detected else "Unknown"


def _get_git_info(working_dir: Path) -> dict[str, str]:
    """Get current git branch and status."""
    info = {"branch": "", "status": ""}

    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5,
            cwd=str(working_dir),
        )
        if result.returncode == 0:
            info["branch"] = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, timeout=5,
            cwd=str(working_dir),
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            if lines:
                modified = sum(1 for l in lines if l.startswith(" M") or l.startswith("M"))
                added = sum(1 for l in lines if l.startswith("A") or l.startswith("??"))
                deleted = sum(1 for l in lines if l.startswith("D") or l.startswith(" D"))
                parts = []
                if modified:
                    parts.append(f"{modified} modified")
                if added:
                    parts.append(f"{added} untracked/new")
                if deleted:
                    parts.append(f"{deleted} deleted")
                info["status"] = ", ".join(parts) if parts else "clean"
            else:
                info["status"] = "clean"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return info


def _get_directory_summary(working_dir: Path) -> str:
    """Get a brief listing of the root directory."""
    lines = []
    try:
        entries = sorted(working_dir.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        for entry in entries[:30]:  # Limit to 30 entries
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                lines.append(f"  📁 {entry.name}/")
            else:
                lines.append(f"  📄 {entry.name}")
    except PermissionError:
        lines.append("  [Permission denied]")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_system_prompt(working_dir: str) -> str:
    """Build the full system prompt with project context."""
    wd = Path(working_dir).resolve()
    project_type = _detect_project_type(wd)
    git_info = _get_git_info(wd)
    dir_summary = _get_directory_summary(wd)

    prompt = f"""You are Lord-Code, an expert AI coding assistant operating in the user's terminal.
You help with software development tasks by reading, writing, and executing code in the user's project.

## Your Capabilities
You have access to tools that let you:
- **read_file**: Read any text file in the project
- **write_file**: Write or create files
- **list_directory**: Explore the project file structure
- **run_command**: Execute shell commands (tests, linting, git, etc.)

Use these tools proactively. Don't just suggest code — actually read, write, and test.

## Rules You MUST Follow
1. ALWAYS read a file with read_file before modifying it — never assume its contents
2. Explain your plan briefly before making changes
3. Match the existing code style of the project
4. Make minimal, targeted changes — don't rewrite entire files unless asked
5. After making changes, suggest running relevant tests or linting
6. If a tool call fails, analyze the error and try a different approach
7. If you're unsure about something, ASK the user rather than guessing
8. When creating new files, include appropriate imports, headers, and documentation
9. Use the project's existing patterns, conventions, and dependencies
10. When showing code, use markdown code blocks with the correct language tag

## Output Formatting
- Use Markdown in your responses (headers, lists, code blocks, bold)
- When explaining code changes, describe WHAT changed and WHY
- Be concise but thorough — no filler text

## Current Project Context
Working directory: {wd}
Project type: {project_type}"""

    if git_info["branch"]:
        prompt += f"\nGit branch: {git_info['branch']}"
    if git_info["status"]:
        prompt += f"\nGit status: {git_info['status']}"

    prompt += f"""

Project root contents:
{dir_summary}
"""

    return prompt
