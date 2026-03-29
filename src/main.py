import sys
import os

# Ensure the root directory is in sys.path before imports
root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from src.ui.rich_ui import ui
from src.config import Config
from src.llm.groq.factory import get_llm_client
from src.cli.chat_loop import ChatLoop
from src.context.project_config import ProjectConfig
from src.context.storage import StorageManager
from src.context.context import build_project_context, detect_languages, get_git_info

def main():
    # Ask for the directory to be used
    current_dir = os.getcwd()
    ui.print(f"Current Directory: [bold cyan]{current_dir}[/bold cyan]")
    try:
        target_dir = input(f"Enter target directory (default: {current_dir}): ").strip()
        if target_dir:
            target_dir = os.path.abspath(os.path.expanduser(target_dir))
            if not os.path.exists(target_dir):
                ui.print(f"[bold red]Error: Directory '{target_dir}' does not exist.[/bold red]")
                sys.exit(1)
            if not os.path.isdir(target_dir):
                ui.print(f"[bold red]Error: '{target_dir}' is not a directory.[/bold red]")
                sys.exit(1)
            os.chdir(target_dir)
            ui.print(f"[bold green]Working directory set to:[/bold green] {os.getcwd()}")
        else:
            ui.print(f"[bold green]Using default directory:[/bold green] {current_dir}")
    except (EOFError, KeyboardInterrupt):
        ui.print("\n[bold red]Operation cancelled.[/bold red]")
        sys.exit(0)

    working_dir = os.getcwd()

    # ── Initialize .lord-code Storage ──
    storage = StorageManager(working_dir)

    # ── Load Project Configuration (.lordcode.yaml) ──
    project_config = ProjectConfig.load(working_dir)
    
    # Use model from config if specified, otherwise default
    model_id = project_config.model or Config.DEFAULT_MODEL
    if model_id not in Config.AVAILABLE_MODELS:
        ui.print(f"[bold yellow]Warning: Model '{model_id}' from .lordcode.yaml not in available models. Using default.[/bold yellow]")
        model_id = Config.DEFAULT_MODEL

    # ── Display Project Info on Startup ──
    _display_project_info(working_dir, model_id, project_config, storage)

    # ── Build Project Context ──
    ui.print("[dim]Gathering project context...[/dim]")
    project_context = build_project_context(working_dir, project_config)

    llm = get_llm_client(model_id)
    chat = ChatLoop(llm, project_context=project_context, project_config=project_config, storage=storage)
    try:
        chat.run()
    finally:
        # Finalize session on any exit
        chat._finalize_session()
        if hasattr(chat, 'total_tokens') and chat.total_tokens['total'] > 0:
            ui.print(f"\nSession Total: {chat.total_tokens['total']} tokens "
                           f"(P: {chat.total_tokens['prompt']}, C: {chat.total_tokens['completion']})")


def _display_project_info(working_dir: str, model_id: str, config: ProjectConfig,
                          storage: StorageManager):
    """Display a rich startup panel with detected project information."""
    lines = []
    
    # Language/framework detection
    langs = detect_languages(working_dir)
    if langs:
        tech = ", ".join(f"{d['framework']}" for d in langs)
        lines.append(f"[bold cyan]Tech Stack:[/bold cyan] {tech}")
    
    # Git info (brief)
    git_info = get_git_info(working_dir)
    if git_info and "Not a git repository" not in git_info:
        # Extract just the branch from the full git info
        for line in git_info.split("\n"):
            if "Branch:" in line:
                lines.append(f"[bold cyan]Git:[/bold cyan] {line.strip().replace('**', '')}")
                break
    
    # Model
    lines.append(f"[bold cyan]Model:[/bold cyan] {model_id}")

    # Config
    if config.custom_instructions:
        lines.append(f"[bold cyan]Config:[/bold cyan] .lordcode.yaml loaded ✓")
    
    # Context limit
    ctx_limit = Config.MODEL_CONTEXT_LIMITS.get(model_id, 128_000)
    lines.append(f"[bold cyan]Context:[/bold cyan] {ctx_limit:,} tokens")

    # .lord-code storage stats
    stats = storage.get_stats()
    storage_parts = []
    if stats["session_count"] > 0:
        storage_parts.append(f"{stats['session_count']} sessions")
    if stats["config_snapshot_count"] > 0:
        storage_parts.append(f"{stats['config_snapshot_count']} configs")
    if stats["has_active_plan"]:
        storage_parts.append("active plan")
    if storage_parts:
        lines.append(f"[bold cyan]Storage:[/bold cyan] {', '.join(storage_parts)}")
    else:
        lines.append(f"[bold cyan]Storage:[/bold cyan] .lord-code/ initialized")

    ui.print_panel("\n".join(lines), title="[bold white]🚀 Lord Code[/bold white]", style="bright_cyan")


if __name__ == "__main__":
    main()
