"""
Slash Command Handler — Processes /commands during a session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.agent.loop import Agent
    from src.cli.formatter import OutputManager
    from src.llm.provider import ProviderManager
    from src.config import Config


# Command descriptions for /help
COMMAND_DESCRIPTIONS = {
    "/help": "Show this help message",
    "/exit, /quit": "End the session",
    "/clear": "Clear conversation history",
    "/mode <mode>": "Change safety mode (paranoid/smart/yolo)",
    "/provider <name>": "Switch LLM provider (groq/openai/anthropic/gemini/ollama)",
    "/model <name>": "Switch model on current provider",
    "/providers": "List all available providers",
    "/cost": "Show token usage and cost",
    "/history": "Show condensed conversation history",
    "/retry": "Re-send the last user message",
    "/verbose": "Toggle verbose mode",
    "/info": "Show current configuration",
}


class CommandHandler:
    """Handles slash commands."""

    def __init__(
        self,
        agent: "Agent",
        output: "OutputManager",
        provider_manager: "ProviderManager",
        config: "Config",
    ) -> None:
        self._agent = agent
        self._output = output
        self._provider = provider_manager
        self._config = config

    async def handle(self, command_str: str) -> Optional[str]:
        """
        Handle a slash command.
        
        Returns:
            "exit" if the session should end,
            "retry" with the message to retry,
            None otherwise.
        """
        parts = command_str.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit"):
            return "exit"

        elif cmd == "/help":
            self._output.display_help(COMMAND_DESCRIPTIONS)

        elif cmd == "/clear":
            self._agent.history.clear()
            self._output.display_success("✅ Conversation history cleared.")

        elif cmd == "/mode":
            return self._handle_mode(arg)

        elif cmd == "/provider":
            return self._handle_provider(arg)

        elif cmd == "/model":
            return self._handle_model(arg)

        elif cmd == "/cost":
            self._output.display_info(self._agent.token_tracker.get_summary())

        elif cmd == "/history":
            history = self._agent.history.get_condensed_history()
            self._output.display_info(f"Conversation History:\n{history}")

        elif cmd == "/retry":
            last_msg = self._agent.history.get_last_user_message()
            if last_msg:
                self._output.display_info(f"Retrying: {last_msg[:80]}...")
                return f"retry:{last_msg}"
            else:
                self._output.display_warning("No previous message to retry.")

        elif cmd == "/verbose":
            self._config.verbose = not self._config.verbose
            state = "ON" if self._config.verbose else "OFF"
            self._output.display_success(f"Verbose mode: {state}")

        elif cmd == "/info":
            self._display_info()

        elif cmd == "/providers":
            self._display_providers()

        else:
            self._output.display_warning(
                f"Unknown command: {cmd}. Type /help for available commands."
            )

        return None

    def _handle_mode(self, arg: str) -> None:
        if arg not in ("paranoid", "smart", "yolo"):
            self._output.display_warning(
                "Usage: /mode <paranoid|smart|yolo>"
            )
            return None
        self._agent.safety.mode = arg
        self._output.display_mode_change(arg)
        return None

    def _handle_provider(self, arg: str) -> None:
        if not arg:
            providers = ", ".join(self._provider.available_providers)
            self._output.display_warning(
                f"Usage: /provider <{providers}>"
            )
            return None
        try:
            msg = self._provider.switch_provider(arg)
            self._agent.llm = self._provider.current
            self._agent.token_tracker.set_model(self._provider.current.model_name)
            self._output.display_provider_info(msg)
        except (ValueError, RuntimeError) as e:
            self._output.display_error(str(e))
        return None

    def _handle_model(self, arg: str) -> None:
        if not arg:
            self._output.display_warning("Usage: /model <model-name>")
            return None
        try:
            msg = self._provider.switch_model(arg)
            self._agent.llm = self._provider.current
            self._agent.token_tracker.set_model(arg)
            self._output.display_provider_info(msg)
        except (ValueError, RuntimeError) as e:
            self._output.display_error(str(e))
        return None

    def _display_info(self) -> None:
        adapter = self._provider.current
        self._output.display_info(
            f"Current Configuration:\n"
            f"  Provider: {adapter.provider_name}\n"
            f"  Model: {adapter.model_name}\n"
            f"  Safety mode: {self._agent.safety.mode.value}\n"
            f"  Streaming: {'ON' if self._config.display.stream else 'OFF'}\n"
            f"  Verbose: {'ON' if self._config.verbose else 'OFF'}\n"
            f"  Working dir: {self._config.working_directory}\n"
            f"  Token usage: {self._agent.token_tracker.get_summary()}"
        )

    def _display_providers(self) -> None:
        from src.config import SUPPORTED_PROVIDERS

        # Show provider table with defaults and status
        provider_defaults = {
            "groq": ("llama-3.3-70b-versatile", "GROQ_API_KEY"),
            "openai": ("gpt-4o-mini", "OPENAI_API_KEY"),
            "anthropic": ("claude-sonnet-4-20250514", "ANTHROPIC_API_KEY"),
            "gemini": ("gemini-2.0-flash", "GEMINI_API_KEY"),
            "ollama": ("llama3.1:8b", "(none — local)"),
        }

        import os
        lines = ["Available Providers:\n"]
        current = self._provider.current_provider_name
        for name in SUPPORTED_PROVIDERS:
            default_model, key_env = provider_defaults.get(name, ("unknown", "unknown"))
            active = "  ✅ " if name == current else "     "

            # Check if API key is set
            if key_env.startswith("("):
                key_status = "local"
            else:
                key_status = "✓ key set" if os.environ.get(key_env) else "✗ key missing"

            lines.append(
                f"{active}{name:<12} model: {default_model:<35} [{key_status}]"
            )

        self._output.display_info("\n".join(lines))
