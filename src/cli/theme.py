"""
Lord Code - Terminal theme and splash screen UI.
"""

from rich.console import Console
from rich.theme import Theme
from rich.rule import Rule
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich import box

from src.config import APP_NAME, APP_VERSION, APP_DESCRIPTION

# ── Theme & Colors ──────────────────────────────────────────────────────────

# Coral-ish color from the screenshot (#ff7f50 is Coral)
LOGO_COLOR = "#ff7f50"

custom_theme = Theme({
    "brand": "bold bright_cyan",
    "version": "dim cyan",
    "command": "bold magenta",
    "prompt": "bold bright_cyan",
    "muted": "dim white",
    "accent": "bold bright_magenta",
    "info": "cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "logo": f"bold {LOGO_COLOR}",
})

console = Console(theme=custom_theme)

# ── Splash Screen ─────────────────────────────────────────────────────────────

def print_splash() -> None:
    """Print the bold Claude-style splash screen."""
    console.clear()
    console.print()

    # 1. Boxed Header
    header_content = Text()
    header_content.append("✴ ", style="logo")
    header_content.append("Welcome to ", style="white")
    header_content.append("Lord Code", style="bold white")
    
    header_panel = Panel(
        header_content,
        box=box.SQUARE,
        border_style="dim white",
        padding=(0, 2),
        expand=False
    )
    console.print(header_panel)
    console.print()

    # 2. Blocky ASCII Logo (LORD CODE)
    # Using a custom bold block arrangement
    logo = Text(style="logo")
    logo.append("██╗      ██████╗ ██████╗ ██████╗ \n")
    logo.append("██║     ██╔═══██╗██╔══██╗██╔══██╗\n")
    logo.append("██║     ██║   ██║██████╔╝██║  ██║\n")
    logo.append("██║     ██║   ██║██╔══██╗██║  ██║\n")
    logo.append("███████╗╚██████╔╝██║  ██║██████╔╝\n")
    logo.append("╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═════╝ \n")
    logo.append("\n")
    logo.append(" ██████╗  ██████╗ ██████╗ ███████╗\n")
    logo.append("██╔════╝ ██╔═══██╗██╔══██╗██╔════╝\n")
    logo.append("██║      ██║   ██║██║  ██║█████╗  \n")
    logo.append("██║      ██║   ██║██║  ██║██╔══╝  \n")
    logo.append("╚██████╗ ╚██████╔╝██████╔╝███████╗\n")
    logo.append(" ╚═════╝  ╚═════╝ ╚═════╝ ╚══════╝")

    console.print(logo)
    console.print()
    console.print()

    # 3. Footer Instruction
    footer = Text()
    footer.append("Press ", style="dim white")
    footer.append("Enter", style="bold white")
    footer.append(" to continue", style="dim white")
    console.print(footer)

# ── Main Chat UI ─────────────────────────────────────────────────────────────

def print_banner() -> None:
    """Print a modern, minimalist banner for the session."""
    header = Text()
    header.append(" ", style="brand")
    header.append("Ｌᵒʳᵈ ᶜᵒᵈᵉ", style="brand")
    header.append(f" v{APP_VERSION}", style="version")
    
    # console.print(Rule(style="dim cyan"))
    console.print(header)
    console.print(f"  {APP_DESCRIPTION}", style="muted")
    console.print(Rule(style="dim cyan"))
    console.print()

def print_goodbye() -> None:
    console.print("\n  [accent]⠿[/accent] [muted]Session ended. Goodbye![/muted]\n")

def print_help(commands: dict[str, str]) -> None:
    console.print("\n  [brand]Commands[/brand]")
    for cmd, desc in sorted(commands.items()):
        console.print(f"  [command]{cmd:<12}[/command] [muted]{desc}[/muted]")
    console.print()

def print_version() -> None:
    console.print(f"  [brand]{APP_NAME}[/brand] [version]v{APP_VERSION}[/version]")

def print_error(message: str) -> None:
    console.print(f"\n  [error]Error:[/error] {message}\n")

def print_status(message: str):
    return console.status(
        f"[brand]{message}[/brand]",
        spinner="dots10",
        spinner_style="brand"
    )

def print_ai_message(message: str) -> None:
    """Print the AI response as a rendered Markdown panel."""
    md = Markdown(message)
    
    panel = Panel(
        md,
        title="[brand]✴ Lord Code[/brand]",
        title_align="left",
        border_style="brand",
        padding=(1, 2),
        box=box.ROUNDED
    )
    
    console.print()
    console.print(panel)
    console.print()
def print_tool_call(name: str, arguments: dict) -> None:
    """Print a tool call with its arguments."""
    arg_str = ", ".join(f"[muted]{k}[/muted]=[info]{v}[/info]" for k, v in arguments.items())
    console.print(f"  [accent]⚙[/accent] [brand]Executing {name}[/brand]({arg_str})...")

def print_terminal_preview(command: str) -> None:
    """Print a terminal-style panel with the command to be executed."""
    panel = Panel(
        Text(f"$ {command}", style="white"),
        title="[muted]Terminal Preview[/muted]",
        title_align="left",
        border_style="dim white",
        padding=(0, 1),
        box=box.SQUARE
    )
    console.print(panel)

def ask_confirmation(message: str) -> bool:
    """Ask for user confirmation (y/n)."""
    console.print(f"\n  [warning]⚠ [/warning] [brand]{message}[/brand] [muted](y/n)[/muted]")
    from prompt_toolkit.shortcuts import confirm
    # Using simple prompt fallback for now, but confirm() is better.
    try:
        choice = input("  ❯ ").strip().lower()
        return choice in ["y", "yes"]
    except:
        return False
