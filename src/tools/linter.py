"""
Automatic Linting & Validation (Feature 3.2)

After any file edit, auto-detects and runs the project's linter/formatter.
Supports --fix mode for simple auto-corrections.
"""

import os
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class LintResult:
    """Result of a linting operation."""
    success: bool
    output: str
    linter_name: str
    file_path: str
    auto_fixed: bool = False


# ── Linter Detection Table ──
# Each entry: (config_indicator, linter_name, fix_command_template, check_command_template)
# Templates use {file} for the file path and {root} for the project root.
LINTER_CONFIGS = [
    # Python — Ruff (preferred)
    {
        "config_check": lambda root: (
            _toml_has_section(os.path.join(root, "pyproject.toml"), "tool.ruff")
            or os.path.exists(os.path.join(root, "ruff.toml"))
            or os.path.exists(os.path.join(root, ".ruff.toml"))
        ),
        "extensions": {".py"},
        "name": "ruff",
        "fix_cmd": ["ruff", "check", "--fix", "{file}"],
        "check_cmd": ["ruff", "check", "{file}"],
    },
    # Python — Black
    {
        "config_check": lambda root: (
            _toml_has_section(os.path.join(root, "pyproject.toml"), "tool.black")
            or os.path.exists(os.path.join(root, ".black"))
        ),
        "extensions": {".py"},
        "name": "black",
        "fix_cmd": ["black", "{file}"],
        "check_cmd": ["black", "--check", "{file}"],
    },
    # Python — Flake8
    {
        "config_check": lambda root: os.path.exists(os.path.join(root, ".flake8")),
        "extensions": {".py"},
        "name": "flake8",
        "fix_cmd": None,  # flake8 doesn't auto-fix
        "check_cmd": ["flake8", "{file}"],
    },
    # JavaScript/TypeScript — ESLint
    {
        "config_check": lambda root: any(
            os.path.exists(os.path.join(root, f))
            for f in [
                ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml",
                "eslint.config.js", "eslint.config.mjs", "eslint.config.ts",
            ]
        ),
        "extensions": {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"},
        "name": "eslint",
        "fix_cmd": ["npx", "eslint", "--fix", "{file}"],
        "check_cmd": ["npx", "eslint", "{file}"],
    },
    # JavaScript/TypeScript — Prettier
    {
        "config_check": lambda root: any(
            os.path.exists(os.path.join(root, f))
            for f in [
                ".prettierrc", ".prettierrc.js", ".prettierrc.json",
                ".prettierrc.yml", ".prettierrc.yaml", "prettier.config.js",
            ]
        ),
        "extensions": {".js", ".jsx", ".ts", ".tsx", ".css", ".html", ".json", ".md"},
        "name": "prettier",
        "fix_cmd": ["npx", "prettier", "--write", "{file}"],
        "check_cmd": ["npx", "prettier", "--check", "{file}"],
    },
    # Rust — rustfmt
    {
        "config_check": lambda root: (
            os.path.exists(os.path.join(root, "rustfmt.toml"))
            or os.path.exists(os.path.join(root, "Cargo.toml"))
        ),
        "extensions": {".rs"},
        "name": "rustfmt",
        "fix_cmd": ["rustfmt", "{file}"],
        "check_cmd": ["rustfmt", "--check", "{file}"],
    },
    # Go — gofmt
    {
        "config_check": lambda root: os.path.exists(os.path.join(root, "go.mod")),
        "extensions": {".go"},
        "name": "gofmt",
        "fix_cmd": ["gofmt", "-w", "{file}"],
        "check_cmd": ["gofmt", "-d", "{file}"],
    },
]

# Fallback Python linters (no config file needed)
PYTHON_FALLBACKS = [
    {"name": "ruff", "fix_cmd": ["ruff", "check", "--fix", "{file}"], "check_cmd": ["ruff", "check", "{file}"]},
    {"name": "flake8", "fix_cmd": None, "check_cmd": ["flake8", "{file}"]},
]


def _toml_has_section(toml_path: str, section: str) -> bool:
    """Check if a TOML file contains a specific section (simple string check)."""
    if not os.path.exists(toml_path):
        return False
    try:
        with open(toml_path, "r") as f:
            content = f.read()
        # Check for [tool.ruff] or [tool.black] style sections
        return f"[{section}]" in content
    except Exception:
        return False


def _is_tool_available(tool_name: str) -> bool:
    """Check if a CLI tool is available on the system."""
    try:
        subprocess.run(
            [tool_name, "--version"],
            capture_output=True, timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def detect_linter(file_path: str, project_root: str) -> Optional[dict]:
    """
    Detect the appropriate linter for a given file based on project config.
    
    Returns a dict with 'name', 'fix_cmd', 'check_cmd' or None if no linter found.
    """
    ext = os.path.splitext(file_path)[1].lower()

    # Check configured linters
    for config in LINTER_CONFIGS:
        if ext not in config["extensions"]:
            continue
        try:
            if config["config_check"](project_root):
                return {
                    "name": config["name"],
                    "fix_cmd": config.get("fix_cmd"),
                    "check_cmd": config["check_cmd"],
                }
        except Exception:
            continue

    # Python fallback — try common linters even without config
    if ext == ".py":
        for fallback in PYTHON_FALLBACKS:
            tool_name = fallback["name"]
            if _is_tool_available(tool_name):
                return fallback

    return None


def run_linter(file_path: str, project_root: str) -> Optional[LintResult]:
    """
    Detect and run the appropriate linter for a file.
    Uses --fix mode when available for simple auto-corrections.
    
    Returns LintResult or None if no linter is applicable.
    """
    linter = detect_linter(file_path, project_root)
    if linter is None:
        return None

    abs_file = os.path.abspath(file_path)
    name = linter["name"]

    # Try fix command first (if available)
    fix_cmd = linter.get("fix_cmd")
    if fix_cmd:
        cmd = [arg.replace("{file}", abs_file) for arg in fix_cmd]
        try:
            result = subprocess.run(
                cmd,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return LintResult(
                    success=True,
                    output=result.stdout.strip() or "No issues found.",
                    linter_name=name,
                    file_path=file_path,
                    auto_fixed=True,
                )
            else:
                # Fix ran but there are still issues
                output = (result.stdout + "\n" + result.stderr).strip()
                return LintResult(
                    success=False,
                    output=output[:2000],  # Truncate
                    linter_name=name,
                    file_path=file_path,
                    auto_fixed=True,  # Some fixes may have been applied
                )
        except FileNotFoundError:
            pass  # Tool not installed, try check-only
        except subprocess.TimeoutExpired:
            return LintResult(
                success=False,
                output=f"{name} timed out after 30s.",
                linter_name=name,
                file_path=file_path,
            )

    # Run check-only command
    check_cmd = linter.get("check_cmd")
    if check_cmd:
        cmd = [arg.replace("{file}", abs_file) for arg in check_cmd]
        try:
            result = subprocess.run(
                cmd,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = (result.stdout + "\n" + result.stderr).strip()
            return LintResult(
                success=result.returncode == 0,
                output=output[:2000] if output else "No issues found.",
                linter_name=name,
                file_path=file_path,
            )
        except FileNotFoundError:
            return None  # Tool not installed
        except subprocess.TimeoutExpired:
            return LintResult(
                success=False,
                output=f"{name} timed out after 30s.",
                linter_name=name,
                file_path=file_path,
            )

    return None
