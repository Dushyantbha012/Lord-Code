"""
Ollama LLM Adapter — Fallback provider using OpenAI-compatible API.

Ollama exposes an OpenAI-compatible endpoint at localhost:11434/v1,
so we reuse the openai AsyncOpenAI client with a different base_url.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional

from openai import AsyncOpenAI, APIConnectionError, APIStatusError

from src.llm.base import (
    LLMAdapter,
    NormalizedResponse,
    StreamChunk,
    StreamEventType,
    StopReason,
    ToolCall,
    TokenUsage,
)


class OllamaAdapter(LLMAdapter):
    """Ollama adapter via OpenAI-compatible API."""

    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ):
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        # Ollama's OpenAI-compatible endpoint
        self._client = AsyncOpenAI(
            base_url=f"{base_url.rstrip('/')}/v1",
            api_key="ollama",  # Ollama doesn't need a real key
        )

    @property
    def provider_name(self) -> str:
        return "ollama"

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
        result = []
        for tc in raw_tool_calls:
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                args = {"_raw": tc.function.arguments}
            result.append(
                ToolCall(id=tc.id, name=tc.function.name, arguments=args)
            )
        return result

    async def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> NormalizedResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._temperature,
            "max_tokens": max_tokens or self._max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except APIConnectionError:
            raise RuntimeError(
                "Cannot connect to Ollama. Is it running? Try: ollama serve"
            )
        except APIStatusError as e:
            raise RuntimeError(f"Ollama API error: {e.message}")

        choice = response.choices[0]
        message = choice.message

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
        except APIConnectionError:
            yield StreamChunk(
                event_type=StreamEventType.DONE,
                content="⚠️ Cannot connect to Ollama. Is it running?",
            )
            return
        except APIStatusError as e:
            yield StreamChunk(
                event_type=StreamEventType.DONE,
                content=f"⚠️ Ollama error: {e.message}",
            )
            return

        tool_call_accumulators: dict[int, dict] = {}
        total_usage = TokenUsage()

        async for chunk in stream:
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue

            delta = choice.delta

            if delta.content:
                yield StreamChunk(
                    event_type=StreamEventType.TEXT_DELTA,
                    content=delta.content,
                )

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_call_accumulators:
                        tool_call_accumulators[idx] = {
                            "id": tc_delta.id or "",
                            "name": (tc_delta.function.name if tc_delta.function and tc_delta.function.name else ""),
                            "arguments": "",
                        }
                        if tc_delta.function and tc_delta.function.name:
                            yield StreamChunk(
                                event_type=StreamEventType.TOOL_CALL_START,
                                tool_call_index=idx,
                                tool_call_id=tc_delta.id,
                                tool_call_name=tc_delta.function.name,
                            )
                    if tc_delta.id:
                        tool_call_accumulators[idx]["id"] = tc_delta.id
                    if tc_delta.function and tc_delta.function.name:
                        tool_call_accumulators[idx]["name"] = tc_delta.function.name
                    if tc_delta.function and tc_delta.function.arguments:
                        tool_call_accumulators[idx]["arguments"] += tc_delta.function.arguments
                        yield StreamChunk(
                            event_type=StreamEventType.TOOL_CALL_DELTA,
                            content=tc_delta.function.arguments,
                            tool_call_index=idx,
                        )

            if choice.finish_reason is not None:
                for idx in sorted(tool_call_accumulators.keys()):
                    acc = tool_call_accumulators[idx]
                    yield StreamChunk(
                        event_type=StreamEventType.TOOL_CALL_END,
                        tool_call_index=idx,
                        tool_call_id=acc["id"],
                        tool_call_name=acc["name"],
                        content=acc["arguments"],
                    )

            if hasattr(chunk, "usage") and chunk.usage:
                total_usage = TokenUsage(
                    input_tokens=chunk.usage.prompt_tokens or 0,
                    output_tokens=chunk.usage.completion_tokens or 0,
                )

        yield StreamChunk(event_type=StreamEventType.DONE, usage=total_usage)

    async def close(self) -> None:
        await self._client.close()
