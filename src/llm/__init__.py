"""LLM adapter package."""

from src.llm.base import (
    LLMAdapter,
    NormalizedResponse,
    StreamChunk,
    StreamEventType,
    StopReason,
    ToolCall,
    TokenUsage,
)
from src.llm.provider import ProviderManager

__all__ = [
    "LLMAdapter",
    "NormalizedResponse",
    "StreamChunk",
    "StreamEventType",
    "StopReason",
    "ToolCall",
    "TokenUsage",
    "ProviderManager",
]

# Adapters are lazily imported by ProviderManager to avoid
# pulling in all SDKs (anthropic, google-genai, etc.) at import time.
# Import them directly if needed:
#   from src.llm.groq_adapter import GroqAdapter
#   from src.llm.openai_adapter import OpenAIAdapter
#   from src.llm.anthropic_adapter import AnthropicAdapter
#   from src.llm.gemini_adapter import GeminiAdapter
#   from src.llm.ollama_adapter import OllamaAdapter
