"""
Groq LLM Adapter — Primary provider using AsyncGroq client.

Uses the Groq Python SDK which mirrors the OpenAI API format.
Supports streaming, tool calling, and rate limit handling.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator, Optional

from groq import AsyncGroq, APIStatusError, APIConnectionError, RateLimitError

from src.llm.base import (
    LLMAdapter,
    NormalizedResponse,
    StreamChunk,
    StreamEventType,
    StopReason,
    ToolCall,
    TokenUsage,
)


class GroqAdapter(LLMAdapter):
    """Groq API adapter using AsyncGroq."""

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ):
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._client = AsyncGroq(api_key=api_key)
        self._last_request_time: float = 0
        self._min_request_interval: float = 0.5  # seconds between requests

    @property
    def provider_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model

    @model_name.setter
    def model_name(self, value: str) -> None:
        self._model = value

    def _normalize_stop_reason(self, finish_reason: Optional[str]) -> StopReason:
        if finish_reason == "stop":
            return StopReason.END_TURN
        elif finish_reason == "tool_calls":
            return StopReason.TOOL_USE
        elif finish_reason == "length":
            return StopReason.MAX_TOKENS
        return StopReason.END_TURN

    def _extract_tool_calls(self, raw_tool_calls: list) -> list[ToolCall]:
        """Convert Groq tool calls to our normalized format."""
        result = []
        for tc in raw_tool_calls:
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {"_raw": tc.function.arguments}
            # Guard: json.loads("null") returns None
            if not isinstance(args, dict):
                args = {}
            result.append(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                )
            )
        return result

    async def _rate_limit_wait(self) -> None:
        """Ensure minimum interval between requests."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.monotonic()

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> NormalizedResponse:
        """Send a non-streaming chat request."""
        await self._rate_limit_wait()

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._temperature,
            "max_tokens": max_tokens or self._max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self._client.chat.completions.create(**kwargs)
                break
            except RateLimitError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** (attempt + 1)
                    await asyncio.sleep(wait_time)
                else:
                    raise RuntimeError(
                        f"Groq rate limit exceeded after {max_retries} retries. "
                        "Try switching to Ollama with /provider ollama"
                    ) from e
            except APIConnectionError as e:
                raise RuntimeError(
                    "Cannot connect to Groq API. Check your internet connection."
                ) from e
            except APIStatusError as e:
                if e.status_code == 401:
                    raise RuntimeError(
                        "Invalid Groq API key. Check your GROQ_API_KEY in .env"
                    ) from e
                raise RuntimeError(f"Groq API error: {e.message}") from e

        choice = response.choices[0]
        message = choice.message

        # Build normalized response
        tool_calls = []
        if message.tool_calls:
            tool_calls = self._extract_tool_calls(message.tool_calls)

        usage = TokenUsage()
        if response.usage:
            usage = TokenUsage(
                input_tokens=response.usage.prompt_tokens or 0,
                output_tokens=response.usage.completion_tokens or 0,
            )

        return NormalizedResponse(
            text_content=message.content,
            tool_calls=tool_calls,
            stop_reason=self._normalize_stop_reason(choice.finish_reason),
            usage=usage,
        )

    async def stream_chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Send a streaming chat request."""
        await self._rate_limit_wait()

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._temperature,
            "max_tokens": max_tokens or self._max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            stream = await self._client.chat.completions.create(**kwargs)
        except RateLimitError:
            yield StreamChunk(
                event_type=StreamEventType.DONE,
                content="⚠️ Groq rate limit hit. Try /provider ollama",
            )
            return
        except APIConnectionError:
            yield StreamChunk(
                event_type=StreamEventType.DONE,
                content="⚠️ Cannot connect to Groq API.",
            )
            return
        except APIStatusError as e:
            yield StreamChunk(
                event_type=StreamEventType.DONE,
                content=f"⚠️ Groq API error: {e.message}",
            )
            return

        # Accumulators for tool calls (they arrive as fragmented deltas)
        tool_call_accumulators: dict[int, dict] = {}
        total_usage = TokenUsage()

        async for chunk in stream:
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue

            delta = choice.delta

            # --- Text content ---
            if delta.content:
                yield StreamChunk(
                    event_type=StreamEventType.TEXT_DELTA,
                    content=delta.content,
                )

            # --- Tool calls (arrive as fragmented deltas) ---
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index

                    if idx not in tool_call_accumulators:
                        # New tool call starting
                        tool_call_accumulators[idx] = {
                            "id": tc_delta.id or "",
                            "name": tc_delta.function.name if tc_delta.function and tc_delta.function.name else "",
                            "arguments": "",
                        }
                        if tc_delta.function and tc_delta.function.name:
                            yield StreamChunk(
                                event_type=StreamEventType.TOOL_CALL_START,
                                tool_call_index=idx,
                                tool_call_id=tc_delta.id,
                                tool_call_name=tc_delta.function.name,
                            )

                    # Accumulate ID if provided
                    if tc_delta.id:
                        tool_call_accumulators[idx]["id"] = tc_delta.id

                    # Accumulate function name if provided
                    if tc_delta.function and tc_delta.function.name:
                        tool_call_accumulators[idx]["name"] = tc_delta.function.name

                    # Accumulate argument fragment
                    if tc_delta.function and tc_delta.function.arguments:
                        tool_call_accumulators[idx]["arguments"] += tc_delta.function.arguments
                        yield StreamChunk(
                            event_type=StreamEventType.TOOL_CALL_DELTA,
                            content=tc_delta.function.arguments,
                            tool_call_index=idx,
                        )

            # --- Check for finish ---
            if choice.finish_reason is not None:
                # Emit completed tool calls
                for idx in sorted(tool_call_accumulators.keys()):
                    acc = tool_call_accumulators[idx]
                    yield StreamChunk(
                        event_type=StreamEventType.TOOL_CALL_END,
                        tool_call_index=idx,
                        tool_call_id=acc["id"],
                        tool_call_name=acc["name"],
                        content=acc["arguments"],
                    )

            # --- Usage info (usually in the last chunk) ---
            try:
                if hasattr(chunk, "usage") and chunk.usage is not None:
                    pt = getattr(chunk.usage, "prompt_tokens", None)
                    ct = getattr(chunk.usage, "completion_tokens", None)
                    if pt is not None or ct is not None:
                        total_usage = TokenUsage(
                            input_tokens=pt or 0,
                            output_tokens=ct or 0,
                        )
            except (AttributeError, TypeError):
                pass

            try:
                if (
                    hasattr(chunk, "x_groq")
                    and chunk.x_groq is not None
                    and hasattr(chunk.x_groq, "usage")
                    and chunk.x_groq.usage is not None
                ):
                    pt = getattr(chunk.x_groq.usage, "prompt_tokens", None)
                    ct = getattr(chunk.x_groq.usage, "completion_tokens", None)
                    if pt is not None or ct is not None:
                        total_usage = TokenUsage(
                            input_tokens=pt or 0,
                            output_tokens=ct or 0,
                        )
            except (AttributeError, TypeError):
                pass

        # Final done event
        yield StreamChunk(
            event_type=StreamEventType.DONE,
            usage=total_usage,
        )

    async def close(self) -> None:
        """Clean up the async client."""
        await self._client.close()
