"""
CLI Interface — Main interactive loop using prompt_toolkit.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import HTML

if TYPE_CHECKING:
    from src.agent.loop import Agent
    from src.cli.commands import CommandHandler
    from src.cli.formatter import OutputManager
    from src.config import Config


def _get_prompt_text(mode: str) -> HTML:
    """Build the prompt with current mode indicator."""
    mode_colors = {
        "paranoid": "ansired",
        "smart": "ansigreen",
        "yolo": "ansiyellow",
    }
    color = mode_colors.get(mode, "ansiwhite")
    return HTML(f'<style fg="{color}">[{mode}]</style> <b>You ❯ </b>')


class CLIInterface:
    """Interactive CLI loop."""

    def __init__(
        self,
        agent: "Agent",
        command_handler: "CommandHandler",
        output: "OutputManager",
        config: "Config",
    ) -> None:
        self._agent = agent
        self._commands = command_handler
        self._output = output
        self._config = config

        # Set up prompt session with history
        history_dir = Path.home() / ".lordcode"
        history_dir.mkdir(exist_ok=True)
        history_file = history_dir / "history"

        self._session = PromptSession(
            history=FileHistory(str(history_file)),
            auto_suggest=AutoSuggestFromHistory(),
            enable_history_search=True,
        )

    async def run(self) -> None:
        """Main interactive loop."""
        while True:
            try:
                # Get user input
                prompt = _get_prompt_text(self._agent.safety.mode.value)
                user_input = await self._session.prompt_async(prompt)

                if not user_input.strip():
                    continue

                # Check for slash commands
                if user_input.strip().startswith("/"):
                    result = await self._commands.handle(user_input.strip())
                    if result == "exit":
                        break
                    elif result and result.startswith("retry:"):
                        # Re-process the retried message
                        retry_msg = result[len("retry:"):]
                        await self._agent.process_message(retry_msg)
                    continue

                # Process through the agent
                await self._agent.process_message(user_input)

            except KeyboardInterrupt:
                self._output.display_info("\nType /exit to quit, or keep chatting.")
                continue

            except EOFError:
                # Ctrl+D on empty input
                break

            except Exception as e:
                self._output.display_error(f"Unexpected error: {e}")
                continue

        # Session ended — show summary
        self._output.display_session_summary(
            message_count=self._agent.history.message_count,
            approved=self._agent.safety.approved_count,
            auto_approved=self._agent.safety.auto_approved_count,
            rejected=self._agent.safety.rejected_count,
            files_modified=self._agent.files_modified,
            commands_run=self._agent.commands_run,
            tracker=self._agent.token_tracker,
        )
