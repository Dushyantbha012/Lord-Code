"""
Intelligent Context Window Management (Feature 2.3)

Tracks token usage, enforces budgets, and auto-summarizes old conversation
to keep within model context limits.
"""

import json
from typing import List, Dict, Any, Optional

# Model context window limits (from Groq docs, March 2026)
MODEL_CONTEXT_LIMITS = {
    "openai/gpt-oss-120b": 128_000,
    "openai/gpt-oss-20b": 128_000,
    "llama-3.3-70b-versatile": 131_072,
    "llama-3.1-8b-instant": 131_072,
    "groq/compound": 131_072,
    "groq/compound-mini": 131_072,
}

DEFAULT_CONTEXT_LIMIT = 128_000


class TokenManager:
    """Manages token counting, budgeting and conversation summarization."""

    def __init__(self, model: str = "openai/gpt-oss-120b", token_budget: Optional[Dict] = None):
        self.model = model
        self.context_limit = MODEL_CONTEXT_LIMITS.get(model, DEFAULT_CONTEXT_LIMIT)
        self._encoder = None
        self._use_tiktoken = True

        # Try to load tiktoken
        try:
            import tiktoken
            self._encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._use_tiktoken = False

        # Budget configuration
        budget = token_budget or {}
        self.system_budget = budget.get("system_prompt", 2500)
        self.file_budget = budget.get("file_contents", 5000)
        
        conv_budget = budget.get("conversation", "auto")
        if conv_budget == "auto" or not isinstance(conv_budget, int):
            # Reserve some headroom for the response
            self.conversation_budget = self.context_limit - self.system_budget - self.file_budget - 4096
        else:
            self.conversation_budget = conv_budget

        # Summarization triggers at 70% of conversation budget
        self.summarize_threshold = int(self.conversation_budget * 0.70)

    def count_tokens(self, text: str) -> int:
        """Count tokens in a string using tiktoken or char-based fallback."""
        if not text:
            return 0
        if self._use_tiktoken and self._encoder:
            return len(self._encoder.encode(text))
        # Fallback: ~4 chars per token
        return max(1, len(text) // 4)

    def count_message_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Count total tokens across a message list (approximation including overhead)."""
        total = 0
        for msg in messages:
            # Each message has ~4 tokens of overhead (role, separators)
            total += 4
            if msg.get("content"):
                total += self.count_tokens(str(msg["content"]))
            if msg.get("tool_calls"):
                total += self.count_tokens(json.dumps(msg["tool_calls"]))
            if msg.get("name"):
                total += self.count_tokens(msg["name"])
        total += 2  # Reply priming tokens
        return total

    def get_budget(self) -> Dict[str, Any]:
        """Return the current token budget breakdown."""
        return {
            "context_limit": self.context_limit,
            "system_prompt": self.system_budget,
            "file_contents": self.file_budget,
            "conversation": self.conversation_budget,
            "summarize_at": self.summarize_threshold,
            "model": self.model,
        }

    def should_summarize(self, messages: List[Dict[str, Any]]) -> bool:
        """Check if conversation tokens exceed the summarization threshold."""
        # Only count non-system messages for conversation budget
        conv_messages = [m for m in messages if m.get("role") != "system"]
        conv_tokens = self.count_message_tokens(conv_messages)
        return conv_tokens > self.summarize_threshold

    def get_conversation_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Get token count for non-system messages."""
        conv_messages = [m for m in messages if m.get("role") != "system"]
        return self.count_message_tokens(conv_messages)

    def summarize_messages(self, messages: List[Dict[str, Any]], llm) -> List[Dict[str, Any]]:
        """
        Summarize older messages to free up context space.
        
        Strategy:
        - Keep the system message(s) intact
        - Keep the last 6 messages intact (recent context)
        - Summarize everything in between into a single summary message
        - Only summarize conversation flow, not tool results
        """
        # Separate system messages
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        # Need at least 8 non-system messages to justify summarization
        if len(non_system) <= 8:
            return messages

        # Messages to summarize (older ones) vs keep (recent ones)
        keep_count = 6
        to_summarize = non_system[:-keep_count]
        to_keep = non_system[-keep_count:]

        # Build a summary of the conversation flow
        conversation_text = []
        for msg in to_summarize:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "user":
                conversation_text.append(f"User asked: {content[:200]}")
            elif role == "assistant":
                if msg.get("tool_calls"):
                    tool_names = [tc["function"]["name"] for tc in msg["tool_calls"]]
                    conversation_text.append(f"Assistant used tools: {', '.join(tool_names)}")
                if content:
                    conversation_text.append(f"Assistant replied: {content[:200]}")
            elif role == "tool":
                # Skip tool results in summary — summarize convo flow only
                pass

        summary_input = "\n".join(conversation_text)

        # Ask LLM to summarize
        try:
            summary_messages = [
                {"role": "system", "content": "You are a conversation summarizer. Summarize the following conversation flow into a brief, dense paragraph. Focus on what was discussed, what decisions were made, and what actions were taken. Be concise."},
                {"role": "user", "content": f"Summarize this conversation:\n\n{summary_input}"}
            ]
            
            summary_text = ""
            for chunk in llm.chat(summary_messages, stream=True, tools=None):
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    summary_text += delta.content

            if not summary_text:
                summary_text = summary_input[:500]  # Fallback

        except Exception:
            # Fallback: just use the raw conversation text, truncated
            summary_text = summary_input[:500]

        # Build the new message list
        summary_msg = {
            "role": "user",
            "content": f"[CONVERSATION SUMMARY - Earlier messages were summarized to save context]\n{summary_text}"
        }

        return system_msgs + [summary_msg] + to_keep

    def update_model(self, model: str):
        """Update the model and recalculate budgets."""
        self.model = model
        self.context_limit = MODEL_CONTEXT_LIMITS.get(model, DEFAULT_CONTEXT_LIMIT)
        # Recalculate conversation budget
        self.conversation_budget = self.context_limit - self.system_budget - self.file_budget - 4096
        self.summarize_threshold = int(self.conversation_budget * 0.70)
