"""
Anthropic LLM Adapter — Claude models (claude-3.5-sonnet, claude-3-haiku, etc.).

Handles the conversion between our standard OpenAI-format messages and
Anthropic's unique message format (system as param, tool_use/tool_result blocks).
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional

import anthropic
from anthropic import AsyncAnthropic, APIStatusError, APIConnectionError, RateLimitError

from src.llm.base import (
    LLMAdapter,
    NormalizedResponse,
    StreamChunk,
    StreamEventType,
    StopReason,
    ToolCall,
    TokenUsage,
)


class AnthropicAdapter(LLMAdapter):
    """Anthropic Claude adapter using AsyncAnthropic."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ):
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._client = AsyncAnthropic(api_key=api_key)

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._model

    @model_name.setter
    def model_name(self, value: str) -> None:
        self._model = value

    # -----------------------------------------------------------------
    # Message format conversion: OpenAI → Anthropic
    # -----------------------------------------------------------------

    def _convert_messages(self, messages: list[dict]) -> tuple[str, list[dict]]:
        """
        Convert OpenAI-format messages to Anthropic format.

        Returns:
            (system_prompt, anthropic_messages)

        Key differences:
        - System message goes to `system` parameter (not in messages)
        - "tool" role messages → "user" message with tool_result content blocks
        - "assistant" with tool_calls → content blocks with type "tool_use"
        - Anthropic requires strictly alternating user/assistant roles
        """
        system_prompt = ""
        anthropic_msgs: list[dict] = []

        for msg in messages:
            role = msg.get("role", "")

            if role == "system":
                system_prompt = msg.get("content", "")
                continue

            elif role == "user":
                anthropic_msgs.append({
                    "role": "user",
                    "content": msg.get("content", ""),
                })

            elif role == "assistant":
                content_blocks = []

                # Add text content if present
                text = msg.get("content")
                if text:
                    content_blocks.append({"type": "text", "text": text})

                # Convert tool_calls to tool_use blocks
                tool_calls = msg.get("tool_calls", [])
                for tc in tool_calls:
                    func = tc.get("function", {})
                    try:
                        input_data = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        input_data = {}
                    if not isinstance(input_data, dict):
                        input_data = {}

                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": func.get("name", ""),
                        "input": input_data,
                    })

                if not content_blocks:
                    content_blocks.append({"type": "text", "text": ""})

                anthropic_msgs.append({
                    "role": "assistant",
                    "content": content_blocks,
                })

            elif role == "tool":
                # Tool results go as user messages with tool_result content blocks
                tool_result_block = {
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": msg.get("content", ""),
                }

                # If the last message is already a user message with tool_result blocks,
                # merge into it (Anthropic requires alternating roles)
                if (
                    anthropic_msgs
                    and anthropic_msgs[-1]["role"] == "user"
                    and isinstance(anthropic_msgs[-1]["content"], list)
                    and all(
                        isinstance(b, dict) and b.get("type") == "tool_result"
                        for b in anthropic_msgs[-1]["content"]
                    )
                ):
                    anthropic_msgs[-1]["content"].append(tool_result_block)
                else:
                    anthropic_msgs.append({
                        "role": "user",
                        "content": [tool_result_block],
                    })

        # Ensure messages start with user role (Anthropic requirement)
        if anthropic_msgs and anthropic_msgs[0]["role"] != "user":
            anthropic_msgs.insert(0, {"role": "user", "content": "Hello"})

        # Merge consecutive same-role messages
        merged: list[dict] = []
        for msg in anthropic_msgs:
            if merged and merged[-1]["role"] == msg["role"]:
                # Merge content
                prev_content = merged[-1]["content"]
                curr_content = msg["content"]

                if isinstance(prev_content, str) and isinstance(curr_content, str):
                    merged[-1]["content"] = prev_content + "\n" + curr_content
                elif isinstance(prev_content, list) and isinstance(curr_content, list):
                    merged[-1]["content"].extend(curr_content)
                elif isinstance(prev_content, str) and isinstance(curr_content, list):
                    merged[-1]["content"] = [{"type": "text", "text": prev_content}] + curr_content
                elif isinstance(prev_content, list) and isinstance(curr_content, str):
                    merged[-1]["content"].append({"type": "text", "text": curr_content})
            else:
                merged.append(msg)

        return system_prompt, merged

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert OpenAI tool schemas to Anthropic format."""
        anthropic_tools = []
        for tool in tools:
            func = tool.get("function", {})
            anthropic_tools.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            })
        return anthropic_tools

    def _normalize_stop_reason(self, stop_reason: Optional[str]) -> StopReason:
        if stop_reason == "end_turn":
            return StopReason.END_TURN
        elif stop_reason == "tool_use":
            return StopReason.TOOL_USE
        elif stop_reason == "max_tokens":
            return StopReason.MAX_TOKENS
        return StopReason.END_TURN

    # -----------------------------------------------------------------
    # API calls
    # -----------------------------------------------------------------

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> NormalizedResponse:
        system_prompt, converted_msgs = self._convert_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": converted_msgs,
            "max_tokens": max_tokens or self._max_tokens,
            "temperature": temperature if temperature is not None else self._temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        try:
            response = await self._client.messages.create(**kwargs)
        except RateLimitError as e:
            raise RuntimeError(
                "Anthropic rate limit exceeded. Wait a moment and try again."
            ) from e
        except APIConnectionError as e:
            raise RuntimeError(
                "Cannot connect to Anthropic API. Check your internet connection."
            ) from e
        except APIStatusError as e:
            if e.status_code == 401:
                raise RuntimeError(
                    "Invalid Anthropic API key. Check your ANTHROPIC_API_KEY in .env"
                ) from e
            raise RuntimeError(f"Anthropic API error: {e.message}") from e

        # Extract content from response
        text_content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else {},
                ))

        usage = TokenUsage(
            input_tokens=response.usage.input_tokens if response.usage else 0,
            output_tokens=response.usage.output_tokens if response.usage else 0,
        )

        return NormalizedResponse(
            text_content=text_content if text_content else None,
            tool_calls=tool_calls,
            stop_reason=self._normalize_stop_reason(response.stop_reason),
            usage=usage,
        )

    async def stream_chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[StreamChunk]:
        system_prompt, converted_msgs = self._convert_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": converted_msgs,
            "max_tokens": max_tokens or self._max_tokens,
            "temperature": temperature if temperature is not None else self._temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        try:
            stream = self._client.messages.stream(**kwargs)
        except (RateLimitError, APIConnectionError, APIStatusError) as e:
            yield StreamChunk(
                event_type=StreamEventType.DONE,
                content=f"⚠️ Anthropic error: {e}",
            )
            return

        total_usage = TokenUsage()
        current_tool_index = -1
        tool_input_buffer = ""

        async with stream as s:
            async for event in s:
                event_type = getattr(event, "type", "")

                if event_type == "message_start":
                    msg = getattr(event, "message", None)
                    if msg and hasattr(msg, "usage") and msg.usage:
                        total_usage = TokenUsage(
                            input_tokens=getattr(msg.usage, "input_tokens", 0) or 0,
                            output_tokens=0,
                        )

                elif event_type == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if block:
                        if block.type == "tool_use":
                            current_tool_index += 1
                            tool_input_buffer = ""
                            yield StreamChunk(
                                event_type=StreamEventType.TOOL_CALL_START,
                                tool_call_index=current_tool_index,
                                tool_call_id=block.id,
                                tool_call_name=block.name,
                            )

                elif event_type == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta:
                        delta_type = getattr(delta, "type", "")
                        if delta_type == "text_delta":
                            yield StreamChunk(
                                event_type=StreamEventType.TEXT_DELTA,
                                content=delta.text,
                            )
                        elif delta_type == "input_json_delta":
                            tool_input_buffer += delta.partial_json
                            yield StreamChunk(
                                event_type=StreamEventType.TOOL_CALL_DELTA,
                                content=delta.partial_json,
                                tool_call_index=current_tool_index,
                            )

                elif event_type == "content_block_stop":
                    if current_tool_index >= 0 and tool_input_buffer:
                        yield StreamChunk(
                            event_type=StreamEventType.TOOL_CALL_END,
                            tool_call_index=current_tool_index,
                            content=tool_input_buffer,
                        )
                        tool_input_buffer = ""

                elif event_type == "message_delta":
                    delta = getattr(event, "delta", None)
                    usage = getattr(event, "usage", None)
                    if usage:
                        total_usage = TokenUsage(
                            input_tokens=total_usage.input_tokens,
                            output_tokens=getattr(usage, "output_tokens", 0) or 0,
                        )

        yield StreamChunk(event_type=StreamEventType.DONE, usage=total_usage)

    async def close(self) -> None:
        await self._client.close()
