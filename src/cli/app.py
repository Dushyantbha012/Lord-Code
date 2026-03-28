"""
Lord Code - Interactive CLI REPL with Claude-style splash screen.
"""

import time
import click
from prompt_toolkit import PromptSession

from src.config import EXIT_COMMANDS, SLASH_COMMANDS
from src.cli.prompt import create_prompt_session
from src.cli.theme import (
    console,
    print_splash,
    print_banner,
    print_goodbye,
    print_help,
    print_version,
    print_ai_message,
    print_status,
)


class CLIApp:
    """Modern interactive CLI for Lord Code."""

    def __init__(self) -> None:
        self.session = create_prompt_session()
        self.running = True

    # ── Input Helpers ──────────────────────────────────────────────────

    def _wait_for_continuation(self) -> None:
        """Wait for the user to press Enter to continue."""
        try:
            # Simple input fallback for the splash screen
            input()
        except (EOFError, KeyboardInterrupt):
            self.running = False

    # ── Command Handlers ────────────────────────────────────────────────

    def _handle_command(self, command: str) -> None:
        """Route a slash command to its handler with a status indicator."""
        cmd = command.strip().lower()

        # Exit commands
        if cmd in EXIT_COMMANDS:
            self.running = False
            return

        with print_status("Processing command..."):
            time.sleep(0.3)

            if cmd == "/help":
                print_help(SLASH_COMMANDS)
                return

            if cmd == "/clear":
                console.clear()
                print_banner()
                return

            if cmd == "/version":
                print_version()
                return

        # Fallback for unknown commands
        console.print(
            f"\n  [warning]⚠ [/warning] Unknown command: [command]{cmd}[/command]"
        )
        console.print("  [muted]Type /help to see available commands.[/muted]\n")

    # ── Main Loop ──────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the REPL loop."""
        # 1. Show Splash Screen
        print_splash()
        self._wait_for_continuation()
        
        if not self.running:
            return

        # 2. Enter Main Chat Session
        console.clear()
        print_banner()

        while self.running:
            try:
                user_input: str = self.session.prompt()
            except KeyboardInterrupt:
                # Ctrl+C → exit gracefully
                self.running = False
                continue
            except EOFError:
                # Ctrl+D → exit gracefully
                self.running = False
                continue

            text = user_input.strip()
            if not text:
                continue

            # Process Slash Commands
            if text.startswith("/"):
                self._handle_command(text)
                continue

            # Process AI Message (Placeholder simulation)
            with print_status("Thinking..."):
                time.sleep(0.5)
                # LLM logic coming soon!
                response = f"I've received your request: '{text}'. Agent logic is being integrated."
                print_ai_message(response)

        print_goodbye()
