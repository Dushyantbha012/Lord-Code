"""
Command Blocklist & Path Validator — Security guardrails.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Hard-blocked command patterns (NEVER execute)
# ---------------------------------------------------------------------------

HARD_BLOCK_PATTERNS: list[tuple[str, str]] = [
    (r"rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?(/|~|\$HOME)", "Recursive force-delete on root/home directory"),
    (r"rm\s+-rf\s+\*", "Recursive force-delete everything"),
    (r"mkfs\.", "Filesystem formatting"),
    (r"dd\s+if=", "Raw disk write"),
    (r":\(\)\{\s*:\|:&\s*\};:", "Fork bomb"),
    (r"chmod\s+777\s+/", "Open permissions on root"),
    (r">\s*/dev/sd", "Direct device write"),
    (r"curl\s+.*\|\s*(bash|sh|zsh)", "Piping remote script to shell"),
    (r"wget\s+.*\|\s*(bash|sh|zsh)", "Piping remote script to shell"),
    (r"format\s+[a-zA-Z]:", "Windows disk format"),
    (r"shutdown\s", "System shutdown"),
    (r"reboot\b", "System reboot"),
    (r"init\s+0", "System halt"),
]

# Pre-compile patterns
_HARD_BLOCKS = [(re.compile(pattern, re.IGNORECASE), desc) for pattern, desc in HARD_BLOCK_PATTERNS]

# ---------------------------------------------------------------------------
# Soft-warning patterns (allowed, but show extra warning)
# ---------------------------------------------------------------------------

SOFT_WARNING_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\b", "⚠️ This command deletes files"),
    (r"\bsudo\b", "⚠️ This runs with elevated privileges"),
    (r"git\s+push\s+--force", "⚠️ This force-pushes and rewrites remote history"),
    (r"git\s+push\s+-f\b", "⚠️ This force-pushes and rewrites remote history"),
    (r"git\s+reset\s+--hard", "⚠️ This discards uncommitted changes permanently"),
    (r"git\s+clean\s+-fd", "⚠️ This removes untracked files permanently"),
    (r"\bnpm\s+publish\b", "⚠️ This publishes a package publicly"),
    (r"\bpip\s+install\b", "⚠️ This installs packages (may modify environment)"),
    (r"\bnpm\s+install\b", "⚠️ This installs packages (modifies node_modules/)"),
]

_SOFT_WARNINGS = [(re.compile(pattern, re.IGNORECASE), desc) for pattern, desc in SOFT_WARNING_PATTERNS]

# ---------------------------------------------------------------------------
# Sensitive files that should get extra warnings on write
# ---------------------------------------------------------------------------

SENSITIVE_FILES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa",
    "authorized_keys", "known_hosts",
    ".ssh/config",
    ".npmrc", ".pypirc",
    "credentials.json", "service-account.json",
    "secrets.yaml", "secrets.yml",
    ".htpasswd",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class BlockCheckResult:
    """Result of checking a command against the blocklist."""
    is_blocked: bool = False
    reason: str = ""
    warnings: list[str] = None  # type: ignore

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


def check_command(command: str) -> BlockCheckResult:
    """
    Check a command against the blocklist.
    
    Returns:
        BlockCheckResult with is_blocked=True if hard-blocked,
        or warnings for soft-block matches.
    """
    # Check hard blocks first
    for pattern, description in _HARD_BLOCKS:
        if pattern.search(command):
            return BlockCheckResult(
                is_blocked=True,
                reason=description,
            )

    # Check soft warnings
    warnings = []
    for pattern, warning in _SOFT_WARNINGS:
        if pattern.search(command):
            warnings.append(warning)

    return BlockCheckResult(is_blocked=False, warnings=warnings)


class PathValidator:
    """Validates and sandboxes file paths to the project directory."""

    def __init__(self, working_dir: str) -> None:
        self._working_dir = Path(working_dir).resolve()

    def validate(self, file_path: str) -> tuple[Path, Optional[str]]:
        """
        Validate a file path.
        
        Returns:
            (resolved_path, error_message)
            error_message is None if path is valid.
        """
        path = Path(file_path)
        if not path.is_absolute():
            path = self._working_dir / path
        resolved = path.resolve()

        try:
            resolved.relative_to(self._working_dir)
        except ValueError:
            return resolved, f"Access denied: Path '{file_path}' escapes the project directory"

        return resolved, None

    def is_sensitive(self, file_path: str) -> Optional[str]:
        """
        Check if a file path refers to a sensitive file.
        Returns warning message or None.
        """
        path = Path(file_path)
        name = path.name

        if name in SENSITIVE_FILES:
            return f"⚠️ '{name}' is a sensitive file (may contain secrets)"

        for sensitive in SENSITIVE_FILES:
            if str(path).endswith(sensitive):
                return f"⚠️ '{sensitive}' is a sensitive file (may contain secrets)"

        return None
