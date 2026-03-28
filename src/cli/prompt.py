"""
Lord Code - Refined input experience.
"""

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

from src.config import SLASH_COMMANDS

# ── prompt_toolkit styling ───────────────────────────────────────────────────

_prompt_style = Style.from_dict({
    "prompt.symbol": "bold ansibrightcyan",
    "prompt.text": "bold ansibrightcyan",
    "completion-menu.completion": "bg:ansiblack ansigray",
    "completion-menu.completion.current": "bg:ansicyan ansiblack",
})

# Minimal prompt symbol
_prompt_message = HTML("<prompt.symbol> › </prompt.symbol>")

# ── Completer for slash commands ─────────────────────────────────────────────

_slash_completer = WordCompleter(
    list(SLASH_COMMANDS.keys()),
    sentence=True,
    ignore_case=True,
)

# ── Custom key bindings ──────────────────────────────────────────────────────

_bindings = KeyBindings()

@_bindings.add(Keys.Escape, Keys.Enter)
def _submit_multiline(event):
    """Allow Esc+Enter or Alt+Enter to submit in multiline mode."""
    event.current_buffer.validate_and_handle()

# ── Session factory ──────────────────────────────────────────────────────────

def create_prompt_session() -> PromptSession:
    """Return a configured PromptSession for the CLI REPL."""
    return PromptSession(
        message=_prompt_message,
        style=_prompt_style,
        completer=_slash_completer,
        multiline=False,
        key_bindings=_bindings,
        mouse_support=False,
        complete_while_typing=True,
    )
