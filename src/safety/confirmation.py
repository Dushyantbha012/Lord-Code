"""
Safety Manager — Tri-mode confirmation system (paranoid / smart / yolo).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax

from src.tools.base import RiskLevel
from src.safety.blocklist import check_command, PathValidator


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class SafetyMode(str, Enum):
    PARANOID = "paranoid"
    SMART = "smart"
    YOLO = "yolo"


class SafetyDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ABORT = "abort"


# ---------------------------------------------------------------------------
# Safety Manager
# ---------------------------------------------------------------------------


class SafetyManager:
    """Manages tool execution safety confirmations."""

    def __init__(self, mode: str = "smart", working_dir: str = ".") -> None:
        self._mode = SafetyMode(mode)
        self._console = Console()
        self._always_approved: set[str] = set()  # Tools auto-approved for the session
        self._path_validator = PathValidator(working_dir)

        # Session stats
        self.approved_count: int = 0
        self.auto_approved_count: int = 0
        self.rejected_count: int = 0

    @property
    def mode(self) -> SafetyMode:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        self._mode = SafetyMode(value)

    def _should_auto_approve(self, tool_name: str, risk: RiskLevel) -> bool:
        """Check if a tool call should be auto-approved based on mode."""
        # Always-approved tools (user already said "always" this session)
        if tool_name in self._always_approved:
            return True

        if self._mode == SafetyMode.YOLO:
            return True
        elif self._mode == SafetyMode.SMART:
            return risk == RiskLevel.SAFE
        elif self._mode == SafetyMode.PARANOID:
            return False

        return False

    def _format_read_file_panel(self, args: dict) -> Panel:
        path = args.get("file_path", "unknown")
        return Panel(
            f"[bold]Path:[/bold] {path}",
            title="📖 Read File",
            border_style="cyan",
        )

    def _format_write_file_panel(self, args: dict) -> Panel:
        path = args.get("file_path", "unknown")
        content = args.get("content", "")
        lines = len(content.splitlines())

        body = f"[bold]Path:[/bold] {path}\n[bold]Lines:[/bold] {lines}"

        # Show a preview of the content (first 20 lines)
        if content:
            preview_lines = content.splitlines()[:20]
            preview = "\n".join(preview_lines)
            if len(content.splitlines()) > 20:
                preview += "\n[dim]... (truncated)[/dim]"
            body += f"\n\n[bold]Preview:[/bold]\n{preview}"

        # Check for sensitive file
        warning = self._path_validator.is_sensitive(path)
        if warning:
            body += f"\n\n[yellow]{warning}[/yellow]"

        return Panel(body, title="✏️  Write File", border_style="yellow")

    def _format_run_command_panel(self, args: dict) -> Panel:
        command = args.get("command", "unknown")

        body = f"[bold]Command:[/bold] {command}"

        # Check for warnings
        result = check_command(command)
        for warning in result.warnings:
            body += f"\n[yellow]{warning}[/yellow]"

        return Panel(body, title="⚡ Execute Command", border_style="red")

    def _format_generic_panel(self, tool_name: str, args: dict) -> Panel:
        body = "\n".join(f"[bold]{k}:[/bold] {v}" for k, v in args.items())
        return Panel(body, title=f"🔧 {tool_name}", border_style="blue")

    async def check(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        risk: RiskLevel,
    ) -> tuple[SafetyDecision, str]:
        """
        Check if a tool call should be executed.
        
        Returns:
            (decision, reason) — reason is empty for APPROVE, or explains rejection.
        """
        # --- Hard block check for run_command ---
        if tool_name == "run_command":
            command = tool_args.get("command", "")
            block_result = check_command(command)
            if block_result.is_blocked:
                self.rejected_count += 1
                return (
                    SafetyDecision.REJECT,
                    f"🚫 BLOCKED: {block_result.reason}\nCommand: {command}",
                )

        # --- Auto-approve check ---
        if self._should_auto_approve(tool_name, risk):
            self.auto_approved_count += 1
            if tool_name in self._always_approved:
                self._console.print(
                    f"  [dim]✅ Auto-approved ({tool_name} — always mode)[/dim]"
                )
            return SafetyDecision.APPROVE, ""

        # --- Show confirmation panel ---
        if tool_name == "read_file":
            panel = self._format_read_file_panel(tool_args)
        elif tool_name == "write_file":
            panel = self._format_write_file_panel(tool_args)
        elif tool_name == "run_command":
            panel = self._format_run_command_panel(tool_args)
        else:
            panel = self._format_generic_panel(tool_name, tool_args)

        self._console.print(panel)

        # Ask for confirmation
        while True:
            answer = Prompt.ask(
                "  Approve?",
                choices=["y", "n", "a"],
                default="y",
            )

            if answer == "y":
                self.approved_count += 1
                return SafetyDecision.APPROVE, ""
            elif answer == "n":
                self.rejected_count += 1
                return (
                    SafetyDecision.REJECT,
                    "User rejected this action. Please suggest an alternative approach or ask the user what they'd prefer.",
                )
            elif answer == "a":
                self._always_approved.add(tool_name)
                self.approved_count += 1
                self._console.print(
                    f"  [dim]✅ '{tool_name}' will be auto-approved for the rest of this session[/dim]"
                )
                return SafetyDecision.APPROVE, ""
