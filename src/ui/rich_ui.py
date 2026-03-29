import sys
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.panel import Panel
from rich.status import Status
from rich.syntax import Syntax
from rich.table import Table
from rich.theme import Theme

# Define a custom theme for Lord Code
LORD_THEME = Theme({
    "info": "dim cyan",
    "warning": "bold yellow",
    "danger": "bold red",
    "success": "bold green",
    "ai": "bold magenta",
    "user": "bold cyan",
    "tool": "bold blue",
    "path": "bold blue",
    "diff.plus": "green",
    "diff.minus": "red",
    "diff.header": "bold white",
    "diff.hunk": "cyan",
})

class RichUI:
    def __init__(self):
        self.console = Console(theme=LORD_THEME)
        self._status: Optional[Status] = None

    def print(self, *args, **kwargs):
        self.console.print(*args, **kwargs)

    def print_markdown(self, text: str):
        self.console.print(Markdown(text))

    def print_panel(self, text: str, title: Optional[str] = None, style: str = "info"):
        self.console.print(Panel(text, title=title, border_style=style))

    def start_spinner(self, message: str):
        if self._status:
            self._status.update(message)
        else:
            self._status = self.console.status(message)
            self._status.start()

    def stop_spinner(self):
        if self._status:
            self._status.stop()
            self._status = None

    def print_diff(self, diff_text: str):
        """Display a diff with red/green coloring."""
        if not diff_text.strip():
            self.console.print("[dim]  (no differences)[/dim]")
            return

        for line in diff_text.splitlines():
            if line.startswith("+++") or line.startswith("---"):
                self.console.print(f"[diff.header]{line}[/diff.header]")
            elif line.startswith("@@"):
                self.console.print(f"[diff.hunk]{line}[/diff.hunk]")
            elif line.startswith("+"):
                self.console.print(f"[diff.plus]{line}[/diff.plus]")
            elif line.startswith("-"):
                self.console.print(f"[diff.minus]{line}[/diff.minus]")
            else:
                self.console.print(f"[dim]{line}[/dim]")

    def print_tool_call(self, name: str, args: Dict[str, Any]):
        arg_str = ", ".join(f"{k}={v}" for k, v in args.items())
        self.console.print(f"[tool]Executing Tool:[/tool] [bold cyan]{name}[/bold cyan]({arg_str})")

    def print_tool_result(self, result: str, name: Optional[str] = None):
        title = f"Tool Result: {name}" if name else "Tool Result"
        
        # Truncate long results for display
        display_result = result[:2000] + "\n[dim]... (truncated)[/dim]" if len(result) > 2000 else result
        
        self.console.print(f"[success]{title}:[/success]")
        
        # Check if the result contains any diff-like blocks
        is_diff = False
        lines = display_result.splitlines()
        for i in range(min(10, len(lines))):
            if lines[i].startswith("--- a/") or lines[i].startswith("+++ b/") or lines[i].startswith("@@ -"):
                is_diff = True
                break
        
        if is_diff:
            self.print_diff(display_result)
        else:
            self.console.print(display_result)

    def live_markdown(self):
        """Returns a context manager for live markdown updates."""
        return Live(Markdown(""), console=self.console, refresh_per_second=10, auto_refresh=False)

    # ── Plan Rendering (Multi-Step Planning) ──────────────────────────────

    def print_plan(self, plan) -> None:
        """Render a plan as a rich Table inside a bordered Panel."""
        from src.agent.planner import StepStatus, PlanStatus

        status_icons = {
            StepStatus.PENDING: "⏳",
            StepStatus.IN_PROGRESS: "🔄",
            StepStatus.DONE: "✅",
            StepStatus.FAILED: "❌",
            StepStatus.SKIPPED: "⏭️",
        }

        table = Table(show_header=True, header_style="bold cyan", box=None, pad_edge=False)
        table.add_column("#", style="dim", width=4)
        table.add_column("Status", width=6, justify="center")
        table.add_column("Step", style="white", ratio=1)
        table.add_column("Result", style="dim", ratio=1, overflow="ellipsis")

        for step in plan.steps:
            icon = status_icons.get(step.status, "?")
            status_style = {
                StepStatus.DONE: "green",
                StepStatus.FAILED: "red",
                StepStatus.IN_PROGRESS: "yellow",
                StepStatus.SKIPPED: "dim",
            }.get(step.status, "white")

            result_text = (step.result or "")[:80]

            table.add_row(
                str(step.index),
                icon,
                f"[{status_style}]{step.description}[/{status_style}]",
                result_text,
            )

        # Plan status badge
        plan_badge = {
            PlanStatus.PENDING_APPROVAL: "[bold yellow]⏳ AWAITING APPROVAL[/bold yellow]",
            PlanStatus.AUTO_APPROVED: "[bold green]✅ AUTO-APPROVED (read-only)[/bold green]",
            PlanStatus.APPROVED: "[bold green]✅ APPROVED[/bold green]",
            PlanStatus.EXECUTING: "[bold cyan]🔄 EXECUTING[/bold cyan]",
            PlanStatus.COMPLETED: "[bold green]🎉 COMPLETED[/bold green]",
            PlanStatus.REJECTED: "[bold red]❌ REJECTED[/bold red]",
            PlanStatus.MODIFIED: "[bold yellow]✏️ MODIFIED[/bold yellow]",
        }.get(plan.status, str(plan.status))

        panel_content = f"{plan_badge}  |  {plan.progress}\n\n"
        # We need to render the table to a string to embed in the Panel
        from io import StringIO
        temp_console = Console(file=StringIO(), theme=LORD_THEME, width=self.console.width - 6)
        temp_console.print(table)
        panel_content += temp_console.file.getvalue()

        self.console.print(Panel(
            panel_content.strip(),
            title=f"[bold white]📋 Plan: {plan.title}[/bold white]",
            border_style="bright_cyan",
            padding=(1, 2),
        ))

    def print_plan_step_update(self, step_index: int, description: str, status: str) -> None:
        """Compact one-line status update for a step transition."""
        icons = {
            "in_progress": "🔄",
            "done": "✅",
            "failed": "❌",
            "skipped": "⏭️",
        }
        icon = icons.get(status, "•")
        color = {
            "in_progress": "yellow",
            "done": "green",
            "failed": "red",
            "skipped": "dim",
        }.get(status, "white")

        self.console.print(
            f"  {icon} [bold]Step {step_index}:[/bold] "
            f"[{color}]{description}[/{color}]"
        )

    def prompt_plan_approval(self) -> str:
        """Styled approval prompt. Returns 'y', 'n', or 'e'."""
        self.console.print()
        self.console.print(
            "[bold yellow]▸ Approve this plan?[/bold yellow]  "
            "[green](y)es[/green] / [red](n)o[/red] / [cyan](e)dit[/cyan]: ",
            end="",
        )
        try:
            response = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            response = "n"
        return response if response in ("y", "n", "e") else "y"

# Global UI instance
ui = RichUI()
