"""
HistoryManager — Conversation history persistence for Lord Code.

Stores each session's messages as streaming JSONL files inside the target
project's .lord-code/history/ directory. Maintains a session index for
quick listing and provides recent-context summaries for system prompt injection.
"""

import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional


class HistoryManager:
    """
    Manages conversation history persistence.

    Each session creates a .jsonl file (one message per line, streamed for
    crash-safety) and registers itself in sessions.json.

    Usage:
        history = HistoryManager(storage)
        history.start_session()
        history.append_message({"role": "user", "content": "Hello"})
        history.end_session(summary="Greeted the assistant", token_count=50)
    """

    def __init__(self, storage):
        """
        Args:
            storage: A StorageManager instance
        """
        self.storage = storage
        self.history_dir = storage.get_dir("history")
        self.sessions_file = os.path.join(self.history_dir, "sessions.json")

        self._session_id: Optional[str] = None
        self._session_file: Optional[str] = None
        self._message_count = 0

    # ── Session Lifecycle ─────────────────────────────────────────────────

    def start_session(self) -> str:
        """
        Start a new conversation session.

        Returns:
            The session ID
        """
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        filename = f"session_{self._session_id}.jsonl"
        self._session_file = os.path.join(self.history_dir, filename)
        self._message_count = 0
        return self._session_id

    def append_message(self, message: Dict[str, Any]) -> None:
        """
        Append a message to the current session's JSONL file.
        Writes immediately (streaming/crash-safe).

        Args:
            message: A message dict (role, content, tool_calls, etc.)
        """
        if not self._session_file:
            return

        try:
            # Build a serializable copy
            record = self._sanitize_message(message)
            record["_ts"] = datetime.now().isoformat()

            with open(self._session_file, "a") as f:
                f.write(json.dumps(record, default=str) + "\n")

            self._message_count += 1
        except Exception:
            pass  # Non-critical

    def end_session(self, summary: str = "", token_count: int = 0) -> None:
        """
        Finalize the current session and update the session index.

        Args:
            summary: A short summary of what happened in this session
            token_count: Total tokens used in this session
        """
        if not self._session_id:
            return

        session_meta = {
            "id": self._session_id,
            "started_at": self._session_id.split("_")[0] + "T" + self._session_id.split("_")[1] if "_" in self._session_id else datetime.now().isoformat(),
            "ended_at": datetime.now().isoformat(),
            "message_count": self._message_count,
            "token_count": token_count,
            "summary": summary,
            "file": os.path.basename(self._session_file) if self._session_file else "",
        }

        # Append to sessions index
        sessions = self._load_sessions_index()
        sessions.append(session_meta)
        self._save_sessions_index(sessions)

        self._session_id = None
        self._session_file = None

    # ── Query ─────────────────────────────────────────────────────────────

    def list_sessions(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        List the last N sessions.

        Args:
            n: Number of sessions to return (most recent first)

        Returns:
            List of session metadata dicts
        """
        sessions = self._load_sessions_index()
        return sessions[-n:][::-1]  # Most recent first

    def load_session(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Load all messages from a past session.

        Args:
            session_id: The session ID to load

        Returns:
            List of message dicts
        """
        # Find the session file
        sessions = self._load_sessions_index()
        session = next((s for s in sessions if s["id"] == session_id), None)
        if not session:
            return []

        filepath = os.path.join(self.history_dir, session.get("file", ""))
        if not os.path.isfile(filepath):
            return []

        messages = []
        try:
            with open(filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        messages.append(json.loads(line))
        except Exception:
            pass

        return messages

    def get_recent_context(self, n_sessions: int = 2) -> str:
        """
        Build a compact summary of the last N sessions for system prompt injection.

        Returns a condensed text block suitable for including in the system prompt
        to give the LLM awareness of previous work on this project.

        Args:
            n_sessions: Number of recent sessions to summarize

        Returns:
            Multi-line string summary, or empty string if no history
        """
        sessions = self.list_sessions(n=n_sessions)
        if not sessions:
            return ""

        lines = ["## Recent Session History"]
        for sess in sessions:
            ended = sess.get("ended_at", "unknown")
            summary = sess.get("summary", "No summary")
            msgs = sess.get("message_count", 0)
            tokens = sess.get("token_count", 0)
            lines.append(
                f"- **{ended[:16]}** ({msgs} msgs, {tokens:,} tokens): {summary}"
            )

        return "\n".join(lines)

    def generate_session_summary(self, messages: List[Dict[str, Any]]) -> str:
        """
        Generate a brief summary from the session's messages.
        Uses a simple heuristic: first user message + tool names used.

        Args:
            messages: The session's message list

        Returns:
            A short summary string
        """
        parts = []

        # First user message
        for msg in messages:
            if msg.get("role") == "user" and msg.get("content"):
                content = msg["content"]
                if not content.startswith("[SYSTEM"):
                    parts.append(content[:100])
                    break

        # Tools used
        tools_used = set()
        for msg in messages:
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    if isinstance(tc, dict) and "function" in tc:
                        tools_used.add(tc["function"].get("name", ""))

        if tools_used:
            # Filter out empty and planning tools
            real_tools = {t for t in tools_used if t and t not in ("create_plan", "update_plan")}
            if real_tools:
                parts.append(f"Tools: {', '.join(sorted(real_tools)[:5])}")

        return " | ".join(parts) if parts else "Empty session"

    # ── Internal ──────────────────────────────────────────────────────────

    def _load_sessions_index(self) -> List[Dict[str, Any]]:
        """Load sessions.json index."""
        if not os.path.isfile(self.sessions_file):
            return []
        try:
            with open(self.sessions_file, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_sessions_index(self, sessions: List[Dict[str, Any]]) -> None:
        """Write sessions.json index."""
        try:
            with open(self.sessions_file, "w") as f:
                json.dump(sessions, f, indent=2)
        except Exception:
            pass

    def _sanitize_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a JSON-serializable copy of a message.
        Strips non-essential fields and truncates large tool results.
        """
        record = {}
        for key, value in message.items():
            if key == "content" and isinstance(value, str) and len(value) > 5000:
                # Truncate very large content (e.g., full file reads)
                record[key] = value[:5000] + f"\n... [truncated, {len(value)} chars total]"
            elif key == "tool_calls" and isinstance(value, list):
                # Keep tool calls but truncate large arguments
                sanitized_calls = []
                for tc in value:
                    if isinstance(tc, dict):
                        tc_copy = dict(tc)
                        if "function" in tc_copy and isinstance(tc_copy["function"], dict):
                            func = dict(tc_copy["function"])
                            args = func.get("arguments", "")
                            if isinstance(args, str) and len(args) > 2000:
                                func["arguments"] = args[:2000] + "... [truncated]"
                            tc_copy["function"] = func
                        sanitized_calls.append(tc_copy)
                    else:
                        sanitized_calls.append(tc)
                record[key] = sanitized_calls
            else:
                record[key] = value

        return record
