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

# Global UI instance
ui = RichUI()
