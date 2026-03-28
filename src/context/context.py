"""
Automatic Project Context Gathering (Feature 2.1)

Collects directory tree, key files, git info, and language/framework detection
to build a rich system prompt for the LLM.
"""

import os
import subprocess
from typing import List, Optional, Dict

from src.context.project_config import ProjectConfig


def get_directory_tree(root: str, config: ProjectConfig, max_depth: int = 3) -> str:
    """Build a directory tree string, respecting .gitignore and config ignored paths."""
    try:
        import pathspec
    except ImportError:
        pathspec = None

    # Load .gitignore patterns
    gitignore_patterns = []
    gitignore_path = os.path.join(root, ".gitignore")
    if os.path.isfile(gitignore_path):
        with open(gitignore_path, "r") as f:
            gitignore_patterns = f.read().splitlines()

    # Combine with config ignored paths
    all_patterns = gitignore_patterns + config.ignored_paths

    spec = None
    if pathspec and all_patterns:
        spec = pathspec.PathSpec.from_lines("gitwildmatch", all_patterns)

    lines = [f"📁 {os.path.basename(root)}/"]
    _walk_tree(root, root, spec, lines, depth=0, max_depth=max_depth)
    return "\n".join(lines)


def _walk_tree(base: str, current: str, spec, lines: list, depth: int, max_depth: int):
    """Recursively walk directory building tree lines."""
    if depth >= max_depth:
        return

    try:
        entries = sorted(os.listdir(current))
    except PermissionError:
        return

    dirs = []
    files = []
    for entry in entries:
        full = os.path.join(current, entry)
        rel = os.path.relpath(full, base)
        if spec and spec.match_file(rel + ("/" if os.path.isdir(full) else "")):
            continue
        if os.path.isdir(full):
            dirs.append(entry)
        else:
            files.append(entry)

    indent = "│   " * depth
    
    for d in dirs:
        lines.append(f"{indent}├── 📁 {d}/")
        _walk_tree(base, os.path.join(current, d), spec, lines, depth + 1, max_depth)
    
    for f in files:
        lines.append(f"{indent}├── {f}")


def get_key_files(root: str, config: ProjectConfig) -> str:
    """Read and summarize key project files (truncated to first 30 lines each)."""
    summaries = []
    for filename in config.key_files:
        filepath = os.path.join(root, filename)
        if os.path.isfile(filepath):
            try:
                with open(filepath, "r", errors="replace") as f:
                    content = f.readlines()[:30]
                content_str = "".join(content).strip()
                if content_str:
                    summaries.append(f"### {filename}\n```\n{content_str}\n```")
            except Exception:
                continue
    
    if not summaries:
        return "No key project files found."
    
    return "\n\n".join(summaries)


def get_git_info(root: str) -> str:
    """Get current branch, last 5 commits, and staged/unstaged change counts."""
    def _run_git(args: List[str]) -> Optional[str]:
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    # Check if it's a git repo
    if not os.path.isdir(os.path.join(root, ".git")):
        return "Not a git repository."

    parts = []

    # Current branch
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if branch:
        parts.append(f"**Branch:** `{branch}`")

    # Last 5 commits
    log = _run_git(["log", "--oneline", "-5", "--no-decorate"])
    if log:
        parts.append(f"**Recent commits:**\n```\n{log}\n```")

    # Staged changes
    staged = _run_git(["diff", "--cached", "--stat"])
    if staged:
        parts.append(f"**Staged changes:**\n```\n{staged}\n```")
    else:
        parts.append("**Staged changes:** None")

    # Unstaged changes
    unstaged = _run_git(["diff", "--stat"])
    if unstaged:
        parts.append(f"**Unstaged changes:**\n```\n{unstaged}\n```")
    else:
        parts.append("**Unstaged changes:** None")

    # Untracked files
    untracked = _run_git(["ls-files", "--others", "--exclude-standard"])
    if untracked:
        files = untracked.splitlines()[:10]
        parts.append(f"**Untracked files ({len(files)} shown):** {', '.join(files)}")

    return "\n".join(parts) if parts else "Git info unavailable."


def detect_languages(root: str) -> List[Dict[str, str]]:
    """Detect languages/frameworks from project config files."""
    detections = []

    indicators = {
        "package.json": ("JavaScript/TypeScript", "Node.js"),
        "tsconfig.json": ("TypeScript", "TypeScript Compiler"),
        "pyproject.toml": ("Python", "Modern Python packaging"),
        "setup.py": ("Python", "Python setuptools"),
        "requirements.txt": ("Python", "pip"),
        "Pipfile": ("Python", "Pipenv"),
        "Cargo.toml": ("Rust", "Cargo"),
        "go.mod": ("Go", "Go Modules"),
        "Gemfile": ("Ruby", "Bundler"),
        "pom.xml": ("Java", "Maven"),
        "build.gradle": ("Java/Kotlin", "Gradle"),
        "composer.json": ("PHP", "Composer"),
        "Makefile": (None, "Make build system"),
        "Dockerfile": (None, "Docker"),
        "docker-compose.yml": (None, "Docker Compose"),
        "docker-compose.yaml": (None, "Docker Compose"),
        ".env": (None, "Environment variables"),
        "vite.config.ts": (None, "Vite"),
        "vite.config.js": (None, "Vite"),
        "webpack.config.js": (None, "Webpack"),
        "next.config.js": (None, "Next.js"),
        "next.config.mjs": (None, "Next.js"),
    }

    seen_frameworks = set()
    for filename, (lang, framework) in indicators.items():
        if os.path.isfile(os.path.join(root, filename)):
            if framework not in seen_frameworks:
                detections.append({
                    "file": filename,
                    "language": lang,
                    "framework": framework,
                })
                seen_frameworks.add(framework)

    return detections


def build_project_context(root: str, config: Optional[ProjectConfig] = None) -> str:
    """
    Orchestrator: builds a condensed project context string for the system prompt.
    """
    if config is None:
        config = ProjectConfig.load(root)

    sections = []

    # Header
    project_name = os.path.basename(os.path.abspath(root))
    sections.append(f"# Project: {project_name}")
    sections.append(f"**Working Directory:** `{os.path.abspath(root)}`\n")

    # Language/Framework Detection
    langs = detect_languages(root)
    if langs:
        lang_str = ", ".join(
            f"{d['language'] or 'Tool'} ({d['framework']})" for d in langs
        )
        sections.append(f"## Tech Stack\n{lang_str}\n")

    # Git Info
    git_info = get_git_info(root)
    if git_info and git_info != "Not a git repository.":
        sections.append(f"## Git Status\n{git_info}\n")

    # Directory Tree
    tree = get_directory_tree(root, config, max_depth=3)
    sections.append(f"## Project Structure\n```\n{tree}\n```\n")

    # Key Files (condensed)
    key_files = get_key_files(root, config)
    if key_files != "No key project files found.":
        sections.append(f"## Key Files\n{key_files}\n")

    # Custom Instructions from .lordcode.yaml
    if config.custom_instructions:
        sections.append(f"## Custom Project Instructions\n{config.custom_instructions}\n")

    # Preferred tools hint
    if config.preferred_tools:
        tools_str = ", ".join(config.preferred_tools)
        sections.append(f"**Preferred tools for this project:** {tools_str}\n")

    return "\n".join(sections)
