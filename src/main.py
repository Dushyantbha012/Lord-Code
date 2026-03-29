"""
Lord-Code — AI Coding Agent.

Entry point for the CLI application.
"""

from __future__ import annotations

import asyncio
import os
import sys

import click

from src.config import load_config
from src.agent.system_prompt import _detect_project_type
from pathlib import Path

VERSION = "0.1.0"


async def main_loop(
    provider: str | None,
    model: str | None,
    mode: str | None,
    no_stream: bool,
    verbose: bool,
    resume: bool,
    fork_session: bool,
) -> None:
    """The async main loop — wires up all components and runs."""
    # Lazy imports to keep CLI startup fast
    from src.cli.formatter import OutputManager
    from src.cli.commands import CommandHandler
    from src.cli.interface import CLIInterface
    from src.llm.provider import ProviderManager
    from src.tools import create_tool_registry
    from src.safety.confirmation import SafetyManager
    from src.agent.loop import Agent

    # Load config
    config = load_config(
        provider=provider,
        model=model,
        mode=mode,
        no_stream=no_stream,
        verbose=verbose,
    )

    # Initialize output first (needed for error display)
    output = OutputManager(theme=config.display.theme)

    # Session Resolution Logic
    import uuid
    import shutil
    import datetime
    
    lord_code_dir = Path(config.working_directory) / ".lord-code"
    sessions_dir = lord_code_dir / "sessions"
    current_session_file = lord_code_dir / "current_session.txt"
    
    session_id = uuid.uuid4().hex[:8]
    
    if resume or fork_session:
        if not sessions_dir.exists() or not list(sessions_dir.glob("*.json")):
            output.display_warning("⚠️ No previous sessions found. Starting a new session.")
        else:
            import questionary
            from questionary import Choice
            
            files = sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            
            # Read last session to set default
            default_session = None
            if current_session_file.exists():
                default_session = current_session_file.read_text().strip()
                
            choices = []
            for f in files:
                sid = f.stem
                dt = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
                mark = "*" if sid == default_session else " "
                choices.append(Choice(f"[{mark}] {sid} (Updated: {dt})", sid))
                
            if len(files) == 1:
                selected_sid = files[0].stem
                if resume:
                    session_id = selected_sid
                else:
                    sessions_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(sessions_dir / f"{selected_sid}.json", sessions_dir / f"{session_id}.json")
            else:
                try:
                    action = "resume" if resume else "fork"
                    selected_sid = await questionary.select(
                        f"Select session to {action}:",
                        choices=choices,
                    ).ask_async()
                    
                    if not selected_sid:
                        sys.exit(0)
                        
                    if resume:
                        session_id = selected_sid
                    else:
                        sessions_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(sessions_dir / f"{selected_sid}.json", sessions_dir / f"{session_id}.json")
                except Exception:
                    sys.exit(0)
                    
    config.session_id = session_id
    
    try:
        current_session_file.parent.mkdir(parents=True, exist_ok=True)
        current_session_file.write_text(session_id)
    except Exception:
        pass

    # Ensure .gitignore covers lord-code
    try:
        gitignore = Path(config.working_directory) / ".gitignore"
        entry = "\n# Lord-Code config\n.lord-code/\n"
        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8")
            if ".lord-code/" not in content and ".lord-code\n" not in content:
                gitignore.write_text(content + entry, encoding="utf-8")
        else:
            gitignore.write_text(entry, encoding="utf-8")
    except Exception:
        pass

    # Display the large ASCII logo at the very top
    output.display_logo()

    # If mode wasn't explicitly provided, prompt for it
    if mode is None:
        import questionary
        from questionary import Choice
        
        try:
            mode_choice = await questionary.select(
                "How should Lord-Code handle tool execution?",
                choices=[
                    Choice("Paranoid : Confirm every tool call (including reads)", "paranoid"),
                    Choice("Smart    : Auto-approve reads, confirm writes & commands (default)", "smart"),
                    Choice("YOLO     : Auto-approve everything (blocklist still active)", "yolo"),
                ],
                default="smart",
            ).ask_async()
            
            if mode_choice:
                config.safety.mode = mode_choice
            else:
                # User pressed cancel or Ctrl+C
                sys.exit(0)
        except Exception:
            sys.exit(0)

    # Initialize provider manager
    try:
        provider_manager = ProviderManager(config)
    except RuntimeError as e:
        output.display_error(str(e))
        sys.exit(1)

    # Initialize tools
    tool_registry = create_tool_registry(
        working_dir=config.working_directory,
        command_timeout=config.safety.command_timeout_seconds,
    )

    # Initialize safety
    safety = SafetyManager(
        mode=config.safety.mode,
        working_dir=config.working_directory,
    )

    # Initialize agent
    agent = Agent(
        llm=provider_manager.current,
        tools=tool_registry,
        safety=safety,
        config=config,
        output=output,
    )

    # Initialize command handler
    command_handler = CommandHandler(
        agent=agent,
        output=output,
        provider_manager=provider_manager,
        config=config,
    )

    # Show session info table
    project_type = _detect_project_type(Path(config.working_directory))
    output.display_session_info(
        version=VERSION,
        model=provider_manager.current.model_name,
        provider=provider_manager.current_provider_name,
        mode=config.safety.mode,
        project_dir=config.working_directory,
        project_type=project_type,
        session_id=config.session_id,
    )

    # Initialize CLI and run
    cli_interface = CLIInterface(
        agent=agent,
        command_handler=command_handler,
        output=output,
        config=config,
    )

    try:
        await cli_interface.run()
    finally:
        await provider_manager.close_all()


@click.command()
@click.option(
    "-p", "--provider",
    type=click.Choice(["groq", "openai", "anthropic", "gemini", "ollama"], case_sensitive=False),
    default=None,
    help="LLM provider to use (groq, openai, anthropic, gemini, ollama).",
)
@click.option(
    "-m", "--model",
    type=str,
    default=None,
    help="Model name to use.",
)
@click.option(
    "--mode",
    type=click.Choice(["paranoid", "smart", "yolo"], case_sensitive=False),
    default=None,
    help="Safety mode.",
)
@click.option(
    "--no-stream",
    is_flag=True,
    default=False,
    help="Disable response streaming.",
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    default=False,
    help="Enable verbose output.",
)
@click.option(
    "-r", "--resume",
    is_flag=True,
    default=False,
    help="Resume a previous chat session.",
)
@click.option(
    "--fork-session",
    is_flag=True,
    default=False,
    help="Fork a previous session into a new parallel state.",
)
@click.version_option(version=VERSION, prog_name="Lord-Code")
def cli(
    provider: str | None,
    model: str | None,
    mode: str | None,
    no_stream: bool,
    verbose: bool,
    resume: bool,
    fork_session: bool,
) -> None:
    """🤖 Lord-Code — AI Coding Agent for your terminal."""
    try:
        asyncio.run(main_loop(provider, model, mode, no_stream, verbose, resume, fork_session))
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    cli()
