"""
Agentic Loop — The core brain of Lord-Code.

Orchestrates: User message → LLM call → Tool execution → Loop until done.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from rich.console import Console

from src.config import Config
from src.llm.base import (
    LLMAdapter,
    NormalizedResponse,
    StreamChunk,
    StreamEventType,
    StopReason,
    ToolCall,
    TokenUsage,
)
from src.tools.registry import ToolRegistry
from src.safety.confirmation import SafetyManager, SafetyDecision
from src.agent.history import HistoryManager, TokenTracker
from src.agent.system_prompt import build_system_prompt
from src.cli.formatter import OutputManager


class Agent:
    """The agentic loop — processes messages, calls tools, and manages conversation."""

    def __init__(
        self,
        llm: LLMAdapter,
        tools: ToolRegistry,
        safety: SafetyManager,
        config: Config,
        output: OutputManager,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.safety = safety
        self.config = config
        self.output = output

        # Build system prompt with project context
        system_prompt = build_system_prompt(config.working_directory)
        self.history = HistoryManager(system_prompt)
        self.token_tracker = TokenTracker()
        self.token_tracker.set_model(llm.model_name)

        # Session stats
        self.files_modified: int = 0
        self.commands_run: int = 0

    async def process_message(self, user_input: str) -> None:
        """
        Process a user message through the full agentic loop.
        
        Flow:
        1. Add user message to history
        2. Call LLM
        3. If text response → display and return
        4. If tool calls → execute tools → feed results → loop
        """
        if not user_input.strip():
            return

        self.history.add_user_message(user_input)
        max_iterations = self.config.safety.max_loop_iterations
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Check context window
            estimated_tokens = self.history.estimate_tokens()
            if estimated_tokens > 100_000:
                self.output.display_warning(
                    f"⚠️ Context is large (~{estimated_tokens:,} tokens). "
                    "Consider using /clear to reset."
                )

            # Get tool schemas
            tool_schemas = self.tools.get_schemas()

            try:
                if self.config.display.stream:
                    response = await self._stream_llm_call(tool_schemas)
                else:
                    response = await self._regular_llm_call(tool_schemas)
            except RuntimeError as e:
                self.output.display_error(str(e))
                return
            except Exception as e:
                self.output.display_error(f"Unexpected error: {type(e).__name__}: {e}")
                return

            # Track usage
            self.token_tracker.add(response.usage)

            # --- Handle response based on stop reason ---

            if response.stop_reason == StopReason.END_TURN:
                # Final text response — display and return
                if response.text_content and not self.config.display.stream:
                    self.output.display_assistant_text(response.text_content)
                self.history.add_assistant_text(response.text_content or "")

                # Show token usage
                if self.config.display.show_token_usage:
                    self.output.display_cost(self.token_tracker)
                return

            elif response.stop_reason == StopReason.TOOL_USE:
                # Process tool calls
                self.history.add_assistant_tool_calls(
                    response.tool_calls,
                    response.text_content,
                )

                if response.text_content and not self.config.display.stream:
                    self.output.display_assistant_text(response.text_content)

                await self._process_tool_calls(response.tool_calls)

            elif response.stop_reason == StopReason.MAX_TOKENS:
                # Response was cut off
                if response.text_content:
                    self.history.add_assistant_text(response.text_content)
                    if not self.config.display.stream:
                        self.output.display_assistant_text(response.text_content)

                self.output.display_warning(
                    "Response was cut off (max tokens). Asking to continue..."
                )
                self.history.add_user_message("Please continue from where you left off.")

            else:
                # Unknown stop reason / error
                if response.text_content:
                    self.output.display_assistant_text(response.text_content)
                return

        # Max iterations reached
        self.output.display_warning(
            f"⚠️ Agent reached maximum iterations ({max_iterations}). Stopping."
        )

    async def _regular_llm_call(self, tool_schemas: list[dict]) -> NormalizedResponse:
        """Non-streaming LLM call."""
        with self.output.spinner("Thinking..."):
            response = await self.llm.chat(
                messages=self.history.get_messages(),
                tools=tool_schemas if tool_schemas else None,
            )
        return response

    async def _stream_llm_call(self, tool_schemas: list[dict]) -> NormalizedResponse:
        """Streaming LLM call with real-time display."""
        text_buffer = ""
        tool_calls: list[ToolCall] = []
        tool_accumulators: dict[int, dict] = {}
        usage = TokenUsage()
        stop_reason = StopReason.END_TURN
        started_text = False

        stream = self.llm.stream_chat(
            messages=self.history.get_messages(),
            tools=tool_schemas if tool_schemas else None,
        )

        async for chunk in stream:
            if chunk.event_type == StreamEventType.TEXT_DELTA:
                if not started_text:
                    self.output.start_stream()
                    started_text = True
                text_buffer += chunk.content
                self.output.stream_token(chunk.content)

            elif chunk.event_type == StreamEventType.TOOL_CALL_START:
                if started_text:
                    self.output.end_stream()
                    started_text = False
                idx = chunk.tool_call_index or 0
                tool_accumulators[idx] = {
                    "id": chunk.tool_call_id or "",
                    "name": chunk.tool_call_name or "",
                    "arguments": "",
                }
                if self.config.display.show_tool_calls:
                    self.output.display_tool_calling(chunk.tool_call_name or "unknown")

            elif chunk.event_type == StreamEventType.TOOL_CALL_DELTA:
                idx = chunk.tool_call_index or 0
                if idx in tool_accumulators:
                    tool_accumulators[idx]["arguments"] += chunk.content

            elif chunk.event_type == StreamEventType.TOOL_CALL_END:
                idx = chunk.tool_call_index or 0
                if idx in tool_accumulators:
                    acc = tool_accumulators[idx]
                    try:
                        args = json.loads(acc["arguments"]) if acc["arguments"] else {}
                    except json.JSONDecodeError:
                        args = {"_raw": acc["arguments"]}
                    # Guard: json.loads("null") returns None
                    if not isinstance(args, dict):
                        args = {}
                    tool_calls.append(ToolCall(
                        id=acc["id"],
                        name=acc["name"],
                        arguments=args,
                    ))
                stop_reason = StopReason.TOOL_USE

            elif chunk.event_type == StreamEventType.DONE:
                if started_text:
                    self.output.end_stream()
                    started_text = False
                if chunk.usage:
                    usage = chunk.usage
                # If no tool calls were collected, it's an end_turn
                if not tool_calls:
                    stop_reason = StopReason.END_TURN
                # Check for error message in done
                if chunk.content and chunk.content.startswith("⚠️"):
                    self.output.display_warning(chunk.content)

        return NormalizedResponse(
            text_content=text_buffer if text_buffer else None,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            usage=usage,
        )

    async def _process_tool_calls(self, tool_calls: list[ToolCall]) -> None:
        """Execute tool calls with safety checks and collect results."""
        for tc in tool_calls:
            tool = self.tools.get(tc.name)
            risk = tool.risk_level if tool else None

            # Guard: ensure arguments is a dict (LLM can send None)
            safe_args = tc.arguments if isinstance(tc.arguments, dict) else {}

            # Display what's being called
            if self.config.display.show_tool_calls and not self.config.display.stream:
                self.output.display_tool_call(tc.name, safe_args)

            # Safety check
            if risk is not None:
                decision, reason = await self.safety.check(tc.name, safe_args, risk)
            else:
                # Unknown tool — let the registry handle the error
                decision = SafetyDecision.APPROVE
                reason = ""

            if decision == SafetyDecision.REJECT:
                self.history.add_tool_result(tc.id, reason)
                self.output.display_tool_rejected(tc.name, reason)
                continue

            if decision == SafetyDecision.ABORT:
                self.history.add_tool_result(tc.id, "User aborted the operation.")
                return

            # Execute the tool
            result = await self.tools.execute(tc.name, safe_args)

            # Display result
            self.output.display_tool_result(tc.name, result)

            # Track stats
            if tc.name == "write_file" and result.success:
                self.files_modified += 1
            elif tc.name == "run_command":
                self.commands_run += 1

            # Add result to history
            self.history.add_tool_result(tc.id, result.output)
