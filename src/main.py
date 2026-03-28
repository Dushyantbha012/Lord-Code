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

    # Show welcome
    project_type = _detect_project_type(Path(config.working_directory))
    output.display_welcome(
        version=VERSION,
        model=provider_manager.current.model_name,
        provider=provider_manager.current_provider_name,
        mode=config.safety.mode,
        project_dir=config.working_directory,
        project_type=project_type,
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
@click.version_option(version=VERSION, prog_name="Lord-Code")
def cli(
    provider: str | None,
    model: str | None,
    mode: str | None,
    no_stream: bool,
    verbose: bool,
) -> None:
    """🤖 Lord-Code — AI Coding Agent for your terminal."""
    try:
        asyncio.run(main_loop(provider, model, mode, no_stream, verbose))
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    cli()
