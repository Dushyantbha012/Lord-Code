"""
Safety Manager — Tri-mode confirmation system (paranoid / smart / yolo).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from rich.console import Console, Group
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
        import difflib
        path = args.get("file_path", "unknown")
        content = args.get("content", "")
        
        resolved_path, error = self._path_validator.validate(path)
        is_new = True
        diff_text = ""
        
        if not error and resolved_path.exists():
            is_new = False
            try:
                old_content = resolved_path.read_text(encoding="utf-8")
                old_lines = old_content.splitlines(keepends=True)
                new_lines = content.splitlines(keepends=True)
                diff = difflib.unified_diff(
                    old_lines, new_lines,
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                    lineterm=""
                )
                diff_text = "".join(diff)
            except Exception:
                pass

        renderables = []
        renderables.append(f"[bold]Path:[/bold] {path}")
        
        warning = self._path_validator.is_sensitive(path)
        if warning:
            renderables.append(f"[yellow]{warning}[/yellow]")
            
        renderables.append("")

        if is_new:
            renderables.append("[green]✨ New file will be created.[/green]")
            preview = content[:1000]
            if len(content) > 1000:
                preview += "\n... (truncated)"
            renderables.append(Syntax(preview, "python", theme="monokai", word_wrap=True))
        else:
            if diff_text:
                num_lines = len(diff_text.splitlines())
                if num_lines > 50:
                    truncated_diff = "\n".join(diff_text.splitlines()[:50]) + f"\n... ({num_lines - 50} more changes)"
                    renderables.append(Syntax(truncated_diff, "diff", theme="monokai", word_wrap=True))
                else:
                    renderables.append(Syntax(diff_text, "diff", theme="monokai", word_wrap=True))
            else:
                renderables.append("[dim](No changes)[/dim]")

        return Panel(Group(*renderables), title="✏️  Review Changes", border_style="yellow")

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
