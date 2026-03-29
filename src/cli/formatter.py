"""
Output Manager — Rich terminal rendering for Lord-Code.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Optional, TYPE_CHECKING

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.status import Status
from rich.theme import Theme
from rich.table import Table
from rich.live import Live
from rich.tree import Tree

if TYPE_CHECKING:
    from src.agent.history import TokenTracker
    from src.tools.base import ToolResult


# Custom theme
LORDCODE_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "tool": "bold magenta",
    "dim": "dim",
})


class OutputManager:
    """Wraps rich.Console for all Lord-Code terminal output."""

    def __init__(self, theme: str = "monokai") -> None:
        self._console = Console(theme=LORDCODE_THEME)
        self._syntax_theme = theme
        self._streaming = False
        self._live_text: Optional[Live] = None
        self._streaming_text = ""
        self._live_tool: Optional[Live] = None
        self._streaming_tool_args = ""
        self._current_tool_name = ""

    @property
    def console(self) -> Console:
        return self._console

    # -----------------------------------------------------------------
    # Assistant output
    # -----------------------------------------------------------------

    def display_assistant_text(self, text: str) -> None:
        """Render a full assistant response as Markdown."""
        self._console.print()
        md = Markdown(text)
        self._console.print(md)
        self._console.print()

    def start_stream(self) -> None:
        """Begin streaming output."""
        self._streaming = True
        self._streaming_text = ""
        self._live_text = Live(Markdown(self._streaming_text), console=self._console, refresh_per_second=15, transient=False)
        self._live_text.start()

    def stream_token(self, token: str) -> None:
        """Print a single streaming token."""
        self._streaming_text += token
        if self._live_text:
            self._live_text.update(Markdown(self._streaming_text))
        else:
            print(token, end="", flush=True)

    def end_stream(self) -> None:
        """End streaming output."""
        if self._streaming:
            if self._live_text:
                self._live_text.stop()
                self._live_text = None
            else:
                print()  # Newline after stream
            self._streaming = False

    # -----------------------------------------------------------------
    # Tool display
    # -----------------------------------------------------------------

    def start_tool_stream(self, tool_name: str) -> None:
        """Begin streaming a tool argument draft."""
        self._current_tool_name = tool_name
        self._streaming_tool_args = ""
        syntax = Syntax("", "json", theme=self._syntax_theme, word_wrap=True)
        panel = Panel(syntax, title=f"⚡ Drafting Call: [tool]{tool_name}[/tool]", border_style="cyan")
        self._live_tool = Live(panel, console=self._console, refresh_per_second=15, transient=True)
        self._live_tool.start()

    def stream_tool_arg(self, chunk: str) -> None:
        """Update the tool argument draft."""
        self._streaming_tool_args += chunk
        if self._live_tool:
            syntax = Syntax(self._streaming_tool_args, "json", theme=self._syntax_theme, word_wrap=True)
            panel = Panel(syntax, title=f"⚡ Drafting Call: [tool]{self._current_tool_name}[/tool]", border_style="cyan")
            self._live_tool.update(panel)

    def end_tool_stream(self) -> None:
        """End the tool argument draft."""
        if self._live_tool:
            self._live_tool.stop()
            self._live_tool = None

    @contextmanager
    def tool_execution_spinner(self, tool_name: str, args: dict):
        """Show a spinner while a tool is executing."""
        args_str = ", ".join(f"{k}={repr(v).replace(chr(92)+'n', ' ⏎ ')[:50]}" for k, v in args.items())
        if len(args_str) > 60:
            args_str = args_str[:57] + "..."
            
        with self._console.status(f"[tool]⚙️  Executing {tool_name}[/tool]([dim]{args_str}[/dim])", spinner="dots"):
            yield

    def display_tool_result_panel(self, tool_name: str, args: dict, result: "ToolResult") -> None:
        """Show the truncated execution result inside a neat panel."""
        style = "green" if result.success else "red"
        icon = "✓" if result.success else "❌"
        
        args_str = ", ".join(f"{k}={repr(v).replace(chr(92)+'n', ' ⏎ ')[:50]}" for k, v in args.items())
        if len(args_str) > 60:
            args_str = args_str[:57] + "..."
            
        output_str = str(result.display_output)
        if len(output_str) > 200:
            output_str = output_str[:197] + "..."
            
        text = f"[bold {style}]{icon} completed[/bold {style}]\n[dim]{output_str}[/dim]"
        panel = Panel(
            text, 
            title=f"[tool]{tool_name}[/tool]({args_str})",
            border_style=style,
            expand=False
        )
        self._console.print(panel)

    def display_tool_rejected(self, tool_name: str, reason: str) -> None:
        """Show that a tool call was rejected."""
        self._console.print(f"  [warning]🚫 {tool_name} rejected: {reason[:100]}[/warning]")

    # -----------------------------------------------------------------
    # Status & info
    # -----------------------------------------------------------------

    def display_error(self, message: str) -> None:
        """Display an error message."""
        self._console.print(f"\n[error]❌ {message}[/error]\n")

    def display_warning(self, message: str) -> None:
        """Display a warning."""
        self._console.print(f"\n[warning]{message}[/warning]\n")

    def display_success(self, message: str) -> None:
        """Display a success message."""
        self._console.print(f"[success]{message}[/success]")

    def display_info(self, message: str) -> None:
        """Display an info message."""
        self._console.print(f"[info]{message}[/info]")

    @contextmanager
    def spinner(self, message: str = "Thinking..."):
        """Show a spinner while waiting."""
        with self._console.status(f"[dim]{message}[/dim]", spinner="dots"):
            yield

    def display_cost(self, tracker: "TokenTracker") -> None:
        """Show token usage and cost."""
        self._console.print(f"  [dim]💰 {tracker.get_summary()}[/dim]")

    # -----------------------------------------------------------------
    # Welcome & session
    # -----------------------------------------------------------------

    def display_logo(self) -> None:
        """Display the large ASCII welcome logo."""
        LOGO = """
██╗      ██████╗ ██████╗ ██████╗ 
██║     ██╔═══██╗██╔══██╗██╔══██╗
██║     ██║   ██║██████╔╝██║  ██║
██║     ██║   ██║██╔══██╗██║  ██║
███████╗╚██████╔╝██║  ██║██████╔╝
╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═════╝ 
 ██████╗ ██████╗ ██████╗ ███████╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝
██║     ██║   ██║██║  ██║█████╗  
██║     ██║   ██║██║  ██║██╔══╝  
╚██████╗╚██████╔╝██████╔╝███████╗
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝
"""
        # Print the large aesthetic logo
        self._console.print(f"[#E27B61]{LOGO}[/#E27B61]")

    def display_session_info(
        self,
        version: str,
        model: str,
        provider: str,
        mode: str,
        project_dir: str,
        project_type: str = "Unknown",
    ) -> None:
        """Display the session info block."""

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style="bold cyan")
        table.add_column()
        table.add_row("🤖 Lord-Code", f"v{version}")
        table.add_row("Model", f"{model} ({provider})")
        table.add_row("Mode", mode)
        table.add_row("Project", project_dir)
        if project_type != "Unknown":
            table.add_row("Detected", project_type)
        table.add_row("Help", "Type /help for commands")

        panel = Panel(
            table,
            border_style="cyan",
            title="[bold cyan]Session Info[/bold cyan]",
            subtitle="[dim]AI Coding Agent[/dim]",
            expand=False,
        )
        self._console.print()
        self._console.print(panel)
        self._console.print()

    def display_session_summary(
        self,
        message_count: int,
        approved: int,
        auto_approved: int,
        rejected: int,
        files_modified: int,
        commands_run: int,
        tracker: "TokenTracker",
    ) -> None:
        """Display the session summary on exit."""
        self._console.print()
        self._console.print("[bold]Session Summary:[/bold]")
        self._console.print(f"  ├── Messages: {message_count}")
        self._console.print(
            f"  ├── Tool calls: {approved + auto_approved + rejected} "
            f"({approved} approved, {auto_approved} auto-approved, {rejected} rejected)"
        )
        self._console.print(f"  ├── Files modified: {files_modified}")
        self._console.print(f"  ├── Commands run: {commands_run}")
        self._console.print(f"  └── {tracker.get_summary()}")
        self._console.print()
        self._console.print("[bold cyan]Goodbye! 👋[/bold cyan]")
        self._console.print()

    # -----------------------------------------------------------------
    # Slash command output
    # -----------------------------------------------------------------

    def display_help(self, commands: dict[str, str]) -> None:
        """Display help for all slash commands."""
        table = Table(title="Available Commands", show_header=True, border_style="cyan")
        table.add_column("Command", style="bold cyan")
        table.add_column("Description")
        for cmd, desc in sorted(commands.items()):
            table.add_row(cmd, desc)
        self._console.print(table)

    def display_mode_change(self, mode: str) -> None:
        """Display mode change confirmation."""
        descriptions = {
            "paranoid": "All tool calls will require confirmation.",
            "smart": "Reads auto-approved, writes and commands require confirmation.",
            "yolo": "All tool calls will be auto-approved.\n"
                    "[yellow]Dangerous command blocklist is still active.[/yellow]",
        }
        desc = descriptions.get(mode, "")
        self._console.print(f"\n[warning]⚠️  Safety Mode Changed: {mode.upper()}[/warning]")
        self._console.print(f"  {desc}")
        self._console.print(f"  Type /mode smart to restore confirmations.\n")

    def display_provider_info(self, message: str) -> None:
        """Display provider/model switch info."""
        self._console.print(f"  [success]✅ {message}[/success]")
