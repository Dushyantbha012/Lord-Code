"""
Conversation History Manager.

Manages the message list in the format expected by the LLM API.
Handles tool call/result pairing and context window tracking.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from src.llm.base import ToolCall, TokenUsage


# ---------------------------------------------------------------------------
# Token tracking
# ---------------------------------------------------------------------------

# Pricing per million tokens (USD)
MODEL_PRICING: dict[str, dict[str, float]] = {
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "llama-4-scout-17b-16e-instruct": {"input": 0.11, "output": 0.34},
    "llama3.1:8b": {"input": 0.0, "output": 0.0},  # Ollama — free
}


class TokenTracker:
    """Tracks token usage and estimates cost across a session."""

    def __init__(self) -> None:
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.request_count: int = 0
        self._model: str = ""

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def set_model(self, model: str) -> None:
        self._model = model

    def add(self, usage: TokenUsage) -> None:
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens
        self.request_count += 1

    def get_cost(self) -> float:
        """Calculate session cost in USD."""
        pricing = MODEL_PRICING.get(self._model, {"input": 0.0, "output": 0.0})
        input_cost = (self.total_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.total_output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def get_summary(self) -> str:
        cost = self.get_cost()
        cost_str = f"${cost:.4f}" if cost > 0 else "Free (local)"
        return (
            f"Tokens: {self.total_input_tokens:,} in / "
            f"{self.total_output_tokens:,} out | "
            f"Requests: {self.request_count} | "
            f"Cost: {cost_str}"
        )


# ---------------------------------------------------------------------------
# History Manager
# ---------------------------------------------------------------------------


class HistoryManager:
    """Manages conversation history in OpenAI/Groq message format."""

    def __init__(self, system_prompt: str) -> None:
        self._system_prompt = system_prompt
        self._messages: list[dict[str, Any]] = []

    @property
    def message_count(self) -> int:
        return len(self._messages)

    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        self._messages.append({"role": "user", "content": content})

    def add_assistant_text(self, content: str) -> None:
        """Add a plain text assistant response."""
        self._messages.append({"role": "assistant", "content": content})

    def add_assistant_tool_calls(
        self,
        tool_calls: list[ToolCall],
        text_content: Optional[str] = None,
    ) -> None:
        """Add an assistant response that contains tool calls."""
        msg: dict[str, Any] = {
            "role": "assistant",
            "content": text_content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in tool_calls
            ],
        }
        self._messages.append(msg)

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        """Add a tool result message."""
        self._messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        })

    def get_messages(self) -> list[dict[str, Any]]:
        """Get the full message list for the API call (system + history)."""
        return [
            {"role": "system", "content": self._system_prompt},
            *self._messages,
        ]

    def get_last_user_message(self) -> Optional[str]:
        """Get the last user message for /retry."""
        for msg in reversed(self._messages):
            if msg["role"] == "user":
                return msg["content"]
        return None

    def clear(self) -> None:
        """Clear conversation history (keeps system prompt)."""
        self._messages.clear()

    def estimate_tokens(self) -> int:
        """Rough estimate of total tokens in the conversation."""
        total_chars = len(self._system_prompt)
        for msg in self._messages:
            content = msg.get("content") or ""
            total_chars += len(str(content))
            if "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    total_chars += len(json.dumps(tc))
        return total_chars // 4  # ~4 chars per token

    def get_condensed_history(self) -> str:
        """Get a condensed view of conversation history for /history command."""
        lines = []
        for i, msg in enumerate(self._messages):
            role = msg["role"]
            if role == "user":
                content = msg["content"]
                if len(content) > 80:
                    content = content[:80] + "..."
                lines.append(f"  [{i+1}] 👤 You: {content}")
            elif role == "assistant":
                if msg.get("tool_calls"):
                    tool_names = [tc["function"]["name"] for tc in msg["tool_calls"]]
                    lines.append(f"  [{i+1}] 🤖 Agent: [calls {', '.join(tool_names)}]")
                else:
                    content = msg.get("content") or ""
                    if len(content) > 80:
                        content = content[:80] + "..."
                    lines.append(f"  [{i+1}] 🤖 Agent: {content}")
            elif role == "tool":
                lines.append(f"  [{i+1}] 🔧 Tool result (id: {msg['tool_call_id'][:12]}...)")
        return "\n".join(lines) if lines else "  (empty)"
