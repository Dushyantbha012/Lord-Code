"""
Google Gemini LLM Adapter — Gemini models (gemini-2.0-flash, gemini-1.5-pro, etc.).

Uses the google-genai SDK for async API calls. Converts between our
standard OpenAI-format messages and Gemini's Content/Part format.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional

from google import genai
from google.genai import types

from src.llm.base import (
    LLMAdapter,
    NormalizedResponse,
    StreamChunk,
    StreamEventType,
    StopReason,
    ToolCall,
    TokenUsage,
)


class GeminiAdapter(LLMAdapter):
    """Google Gemini adapter using google-genai SDK."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ):
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._client = genai.Client(api_key=api_key)

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    @model_name.setter
    def model_name(self, value: str) -> None:
        self._model = value

    # -----------------------------------------------------------------
    # Message format conversion: OpenAI → Gemini
    # -----------------------------------------------------------------

    def _convert_messages(self, messages: list[dict]) -> tuple[str, list[types.Content]]:
        """
        Convert OpenAI-format messages to Gemini Content format.

        Returns:
            (system_instruction, contents)
        """
        system_prompt = ""
        contents: list[types.Content] = []

        for msg in messages:
            role = msg.get("role", "")

            if role == "system":
                system_prompt = msg.get("content", "")
                continue

            elif role == "user":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=msg.get("content", ""))],
                ))

            elif role == "assistant":
                parts: list[types.Part] = []

                # Text content
                text = msg.get("content")
                if text:
                    parts.append(types.Part.from_text(text=text))

                # Tool calls → function_call parts
                tool_calls = msg.get("tool_calls", [])
                for tc in tool_calls:
                    func = tc.get("function", {})
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}
                    if not isinstance(args, dict):
                        args = {}
                    parts.append(types.Part.from_function_call(
                        name=func.get("name", ""),
                        args=args,
                    ))

                if not parts:
                    parts.append(types.Part.from_text(text=""))

                contents.append(types.Content(role="model", parts=parts))

            elif role == "tool":
                # Tool result → function_response part
                tool_call_id = msg.get("tool_call_id", "")
                content = msg.get("content", "")

                # Find the function name from the previous assistant message
                func_name = self._find_function_name(messages, tool_call_id)

                response_part = types.Part.from_function_response(
                    name=func_name,
                    response={"result": content},
                )

                # Merge consecutive tool results into one user turn
                if (
                    contents
                    and contents[-1].role == "user"
                    and any(
                        hasattr(p, "function_response") and p.function_response
                        for p in contents[-1].parts
                    )
                ):
                    contents[-1].parts.append(response_part)
                else:
                    contents.append(types.Content(
                        role="user",
                        parts=[response_part],
                    ))

        return system_prompt, contents

    def _find_function_name(self, messages: list[dict], tool_call_id: str) -> str:
        """Find the function name for a given tool_call_id."""
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    if tc.get("id") == tool_call_id:
                        return tc.get("function", {}).get("name", "unknown")
        return "unknown"

    def _convert_tools(self, tools: list[dict]) -> list[types.Tool]:
        """Convert OpenAI tool schemas to Gemini function declarations."""
        declarations = []
        for tool in tools:
            func = tool.get("function", {})
            params = func.get("parameters", {"type": "object", "properties": {}})

            declarations.append(types.FunctionDeclaration(
                name=func.get("name", ""),
                description=func.get("description", ""),
                parameters=params,
            ))

        return [types.Tool(function_declarations=declarations)]

    def _normalize_stop_reason(self, finish_reason) -> StopReason:
        """Convert Gemini finish reason to our enum."""
        reason_str = str(finish_reason).lower() if finish_reason else ""
        if "stop" in reason_str:
            return StopReason.END_TURN
        elif "max_tokens" in reason_str or "length" in reason_str:
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
        system_prompt, contents = self._convert_messages(messages)

        config = types.GenerateContentConfig(
            temperature=temperature if temperature is not None else self._temperature,
            max_output_tokens=max_tokens or self._max_tokens,
        )
        if system_prompt:
            config.system_instruction = system_prompt
        if tools:
            config.tools = self._convert_tools(tools)
            config.automatic_function_calling = types.AutomaticFunctionCallingConfig(
                disable=True
            )

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            error_str = str(e)
            if "401" in error_str or "API key" in error_str.lower():
                raise RuntimeError(
                    "Invalid Gemini API key. Check your GEMINI_API_KEY in .env"
                ) from e
            raise RuntimeError(f"Gemini API error: {e}") from e

        # Process response
        text_content = ""
        tool_calls = []

        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if part.text:
                        text_content += part.text
                    elif part.function_call:
                        fc = part.function_call
                        args = dict(fc.args) if fc.args else {}
                        tool_calls.append(ToolCall(
                            id=f"call_{fc.name}_{len(tool_calls)}",
                            name=fc.name,
                            arguments=args,
                        ))

            stop_reason = self._normalize_stop_reason(
                getattr(candidate, "finish_reason", None)
            )
        else:
            stop_reason = StopReason.END_TURN

        # Check for tool calls in stop reason
        if tool_calls:
            stop_reason = StopReason.TOOL_USE

        usage = TokenUsage()
        if response.usage_metadata:
            usage = TokenUsage(
                input_tokens=getattr(response.usage_metadata, "prompt_token_count", 0) or 0,
                output_tokens=getattr(response.usage_metadata, "candidates_token_count", 0) or 0,
            )

        return NormalizedResponse(
            text_content=text_content if text_content else None,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            usage=usage,
        )

    async def stream_chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[StreamChunk]:
        system_prompt, contents = self._convert_messages(messages)

        config = types.GenerateContentConfig(
            temperature=temperature if temperature is not None else self._temperature,
            max_output_tokens=max_tokens or self._max_tokens,
        )
        if system_prompt:
            config.system_instruction = system_prompt
        if tools:
            config.tools = self._convert_tools(tools)
            config.automatic_function_calling = types.AutomaticFunctionCallingConfig(
                disable=True
            )

        try:
            stream = self._client.aio.models.generate_content_stream(
                model=self._model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            yield StreamChunk(
                event_type=StreamEventType.DONE,
                content=f"⚠️ Gemini error: {e}",
            )
            return

        total_usage = TokenUsage()
        tool_call_index = -1

        try:
            async for chunk in stream:
                if chunk.candidates:
                    candidate = chunk.candidates[0]
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if part.text:
                                yield StreamChunk(
                                    event_type=StreamEventType.TEXT_DELTA,
                                    content=part.text,
                                )
                            elif part.function_call:
                                tool_call_index += 1
                                fc = part.function_call
                                args = dict(fc.args) if fc.args else {}
                                args_json = json.dumps(args)

                                yield StreamChunk(
                                    event_type=StreamEventType.TOOL_CALL_START,
                                    tool_call_index=tool_call_index,
                                    tool_call_id=f"call_{fc.name}_{tool_call_index}",
                                    tool_call_name=fc.name,
                                )
                                yield StreamChunk(
                                    event_type=StreamEventType.TOOL_CALL_DELTA,
                                    content=args_json,
                                    tool_call_index=tool_call_index,
                                )
                                yield StreamChunk(
                                    event_type=StreamEventType.TOOL_CALL_END,
                                    tool_call_index=tool_call_index,
                                    tool_call_id=f"call_{fc.name}_{tool_call_index}",
                                    tool_call_name=fc.name,
                                    content=args_json,
                                )

                if chunk.usage_metadata:
                    total_usage = TokenUsage(
                        input_tokens=getattr(chunk.usage_metadata, "prompt_token_count", 0) or 0,
                        output_tokens=getattr(chunk.usage_metadata, "candidates_token_count", 0) or 0,
                    )
        except Exception as e:
            yield StreamChunk(
                event_type=StreamEventType.DONE,
                content=f"⚠️ Gemini stream error: {e}",
            )
            return

        yield StreamChunk(event_type=StreamEventType.DONE, usage=total_usage)

    async def close(self) -> None:
        """Nothing to close — genai client doesn't need explicit cleanup."""
        pass
