"""
Smart File Search Tools (Feature 2.2)

Provides advanced search capabilities: fuzzy file finding, content search,
symbol definition search, git diff, and git log.
"""

import os
import re
import subprocess
import fnmatch
from typing import List, Optional


def find_files(name_pattern: str, path: str = ".") -> str:
    """
    Find files matching a name/glob pattern, respecting .gitignore.
    Uses git ls-files when possible for gitignore awareness.
    """
    try:
        # Try git ls-files first (respects .gitignore automatically)
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=path if os.path.isabs(path) else os.path.abspath(path),
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            all_files = result.stdout.strip().splitlines()
        else:
            # Fallback: manual walk
            all_files = _walk_all_files(path)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        all_files = _walk_all_files(path)

    # Filter by pattern
    matches = []
    for f in all_files:
        basename = os.path.basename(f)
        if fnmatch.fnmatch(basename, name_pattern) or fnmatch.fnmatch(f, name_pattern):
            matches.append(f)
        # Also try case-insensitive
        elif fnmatch.fnmatch(basename.lower(), name_pattern.lower()):
            matches.append(f)

    if not matches:
        return f"No files found matching pattern: {name_pattern}"

    if len(matches) > 50:
        return f"Found {len(matches)} files (showing first 50):\n" + "\n".join(matches[:50])

    return f"Found {len(matches)} file(s):\n" + "\n".join(matches)


def _walk_all_files(path: str) -> List[str]:
    """Walk directory manually, skipping common ignored dirs."""
    skip = {".git", "__pycache__", "node_modules", "venv", ".venv", "dist", "build", ".tox"}
    files = []
    root_abs = os.path.abspath(path)
    for dirpath, dirnames, filenames in os.walk(root_abs):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for f in filenames:
            rel = os.path.relpath(os.path.join(dirpath, f), root_abs)
            files.append(rel)
    return files


def search_in_files(query: str, path: str = ".", file_pattern: str = "*") -> str:
    """
    Search for text content across project files.
    Returns file:line:content matches, capped at 50 results.
    """
    root = os.path.abspath(path)
    matches = []
    max_results = 50

    # Try ripgrep first, then grep, then Python fallback
    rg_result = _try_ripgrep(query, root, file_pattern, max_results)
    if rg_result is not None:
        return rg_result

    grep_result = _try_grep(query, root, file_pattern, max_results)
    if grep_result is not None:
        return grep_result

    # Python fallback
    try:
        for fpath in _walk_all_files(root):
            if file_pattern != "*" and not fnmatch.fnmatch(fpath, file_pattern):
                continue
            full = os.path.join(root, fpath)
            try:
                with open(full, "r", errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        if query.lower() in line.lower():
                            matches.append(f"{fpath}:{i}: {line.rstrip()}")
                            if len(matches) >= max_results:
                                break
            except (PermissionError, IsADirectoryError, UnicodeDecodeError):
                continue
            if len(matches) >= max_results:
                break
    except Exception as e:
        return f"Error searching files: {str(e)}"

    if not matches:
        return f"No matches found for: {query}"

    header = f"Found {len(matches)} match(es)"
    if len(matches) >= max_results:
        header += f" (showing first {max_results})"
    return header + ":\n" + "\n".join(matches)


def _try_ripgrep(query: str, root: str, file_pattern: str, max_results: int) -> Optional[str]:
    """Try using ripgrep for fast search."""
    try:
        cmd = ["rg", "--no-heading", "-n", "-i", "--max-count", str(max_results)]
        if file_pattern != "*":
            cmd.extend(["-g", file_pattern])
        cmd.append(query)
        result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=15)
        if result.returncode <= 1:
            output = result.stdout.strip()
            if not output:
                return f"No matches found for: {query}"
            lines = output.splitlines()[:max_results]
            return f"Found {len(lines)} match(es):\n" + "\n".join(lines)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _try_grep(query: str, root: str, file_pattern: str, max_results: int) -> Optional[str]:
    """Try using grep for search."""
    try:
        exclude_dirs = "--exclude-dir=venv --exclude-dir=.venv --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=__pycache__ --exclude-dir=dist --exclude-dir=build"
        cmd = f'grep -rn -i {exclude_dirs} --include="{file_pattern}" "{query}" "{root}" | head -{max_results}'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
        if result.returncode <= 1:
            output = result.stdout.strip()
            if not output:
                return f"No matches found for: {query}"
            # Make paths relative
            lines = []
            for line in output.splitlines()[:max_results]:
                line = line.replace(root + "/", "")
                lines.append(line)
            return f"Found {len(lines)} match(es):\n" + "\n".join(lines)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def find_definition(symbol: str, path: str = ".") -> str:
    """
    Find where a function, class, or variable is defined.
    Searches using language-aware regex patterns for Python, JS/TS, Rust, Go, etc.
    """
    patterns = [
        # Python
        (r"^\s*(async\s+)?def\s+" + re.escape(symbol) + r"\s*\(", "*.py"),
        (r"^\s*class\s+" + re.escape(symbol) + r"[\s(:]", "*.py"),
        (r"^\s*" + re.escape(symbol) + r"\s*=", "*.py"),
        # JavaScript / TypeScript
        (r"^\s*(export\s+)?(async\s+)?function\s+" + re.escape(symbol) + r"\s*\(", "*.{js,ts,jsx,tsx}"),
        (r"^\s*(export\s+)?(const|let|var)\s+" + re.escape(symbol) + r"\s*=", "*.{js,ts,jsx,tsx}"),
        (r"^\s*(export\s+)?class\s+" + re.escape(symbol) + r"[\s{]", "*.{js,ts,jsx,tsx}"),
        # Rust
        (r"^\s*(pub\s+)?fn\s+" + re.escape(symbol) + r"\s*[<(]", "*.rs"),
        (r"^\s*(pub\s+)?struct\s+" + re.escape(symbol) + r"[\s{<]", "*.rs"),
        (r"^\s*(pub\s+)?enum\s+" + re.escape(symbol) + r"[\s{<]", "*.rs"),
        # Go
        (r"^\s*func\s+(\([^)]*\)\s+)?" + re.escape(symbol) + r"\s*\(", "*.go"),
        (r"^\s*type\s+" + re.escape(symbol) + r"\s+(struct|interface)", "*.go"),
    ]

    root = os.path.abspath(path)
    results = []

    for fpath in _walk_all_files(root):
        full = os.path.join(root, fpath)
        ext = os.path.splitext(fpath)[1]
        try:
            with open(full, "r", errors="replace") as f:
                lines = f.readlines()
            for i, line in enumerate(lines, 1):
                for pattern, glob_filter in patterns:
                    # Check if file extension matches the glob filter
                    if not _ext_matches_glob(ext, glob_filter):
                        continue
                    if re.search(pattern, line):
                        results.append(f"{fpath}:{i}: {line.rstrip()}")
                        break
        except (PermissionError, IsADirectoryError, UnicodeDecodeError):
            continue

    if not results:
        return f"No definition found for: {symbol}"

    return f"Found {len(results)} definition(s) for '{symbol}':\n" + "\n".join(results)


def _ext_matches_glob(ext: str, glob_filter: str) -> bool:
    """Check if a file extension matches a glob pattern like *.py or *.{js,ts}."""
    if not ext:
        return False
    # Handle brace expansion: *.{js,ts,jsx,tsx}
    if "{" in glob_filter:
        inner = glob_filter.split("{")[1].split("}")[0]
        extensions = ["." + e.strip() for e in inner.split(",")]
        return ext in extensions
    # Simple glob: *.py
    return fnmatch.fnmatch(ext, glob_filter.replace("*", ""))


def get_git_diff() -> str:
    """Show current uncommitted changes (both staged and unstaged)."""
    try:
        # Unstaged changes
        unstaged = subprocess.run(
            ["git", "diff"],
            capture_output=True, text=True, timeout=10,
        )
        # Staged changes
        staged = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True, text=True, timeout=10,
        )

        parts = []
        if staged.stdout.strip():
            diff = staged.stdout.strip()
            if len(diff) > 3000:
                diff = diff[:3000] + "\n... (truncated)"
            parts.append(f"=== STAGED CHANGES ===\n{diff}")
        
        if unstaged.stdout.strip():
            diff = unstaged.stdout.strip()
            if len(diff) > 3000:
                diff = diff[:3000] + "\n... (truncated)"
            parts.append(f"=== UNSTAGED CHANGES ===\n{diff}")

        if not parts:
            return "No uncommitted changes."

        return "\n\n".join(parts)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return f"Error getting git diff: {str(e)}"


def get_git_log(n: int = 10) -> str:
    """Show the last N commits with details."""
    try:
        n = min(max(1, n), 50)  # Clamp between 1 and 50
        result = subprocess.run(
            ["git", "log", f"-{n}", "--pretty=format:%h %an %ar %s"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return f"Error: {result.stderr.strip()}"
        
        output = result.stdout.strip()
        if not output:
            return "No commits found."
        
        return f"Last {n} commits:\n{output}"
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return f"Error getting git log: {str(e)}"
