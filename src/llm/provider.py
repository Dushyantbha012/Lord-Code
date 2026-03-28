"""
Provider Manager — Holds LLM adapters and supports runtime switching.

Supports: groq (default), openai, anthropic, gemini, ollama
"""

from __future__ import annotations

from typing import Optional

from src.config import Config, SUPPORTED_PROVIDERS
from src.llm.base import LLMAdapter


class ProviderManager:
    """Manages LLM provider adapters and supports runtime switching."""

    def __init__(self, config: Config):
        self._config = config
        self._adapters: dict[str, LLMAdapter] = {}
        self._current_provider: str = config.llm.default_provider

        # Initialize the default provider
        self._init_provider(config.llm.default_provider)

    def _init_provider(self, provider: str) -> None:
        """Initialize a provider adapter if not already initialized."""
        if provider in self._adapters:
            return

        if provider == "groq":
            from src.llm.groq_adapter import GroqAdapter

            api_key = self._config.llm.groq.api_key
            if not api_key:
                raise RuntimeError(
                    "GROQ_API_KEY not found. Set it in your .env file.\n"
                    "Get a free key at: https://console.groq.com"
                )
            self._adapters["groq"] = GroqAdapter(
                api_key=api_key,
                model=self._config.llm.groq.model,
                max_tokens=self._config.llm.groq.max_tokens,
                temperature=self._config.llm.groq.temperature,
            )

        elif provider == "openai":
            from src.llm.openai_adapter import OpenAIAdapter

            api_key = self._config.llm.openai.api_key
            if not api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY not found. Set it in your .env file.\n"
                    "Get a key at: https://platform.openai.com/api-keys"
                )
            self._adapters["openai"] = OpenAIAdapter(
                api_key=api_key,
                model=self._config.llm.openai.model,
                max_tokens=self._config.llm.openai.max_tokens,
                temperature=self._config.llm.openai.temperature,
            )

        elif provider == "anthropic":
            from src.llm.anthropic_adapter import AnthropicAdapter

            api_key = self._config.llm.anthropic.api_key
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY not found. Set it in your .env file.\n"
                    "Get a key at: https://console.anthropic.com/settings/keys"
                )
            self._adapters["anthropic"] = AnthropicAdapter(
                api_key=api_key,
                model=self._config.llm.anthropic.model,
                max_tokens=self._config.llm.anthropic.max_tokens,
                temperature=self._config.llm.anthropic.temperature,
            )

        elif provider == "gemini":
            from src.llm.gemini_adapter import GeminiAdapter

            api_key = self._config.llm.gemini.api_key
            if not api_key:
                raise RuntimeError(
                    "GEMINI_API_KEY not found. Set it in your .env file.\n"
                    "Get a key at: https://aistudio.google.com/apikey"
                )
            self._adapters["gemini"] = GeminiAdapter(
                api_key=api_key,
                model=self._config.llm.gemini.model,
                max_tokens=self._config.llm.gemini.max_tokens,
                temperature=self._config.llm.gemini.temperature,
            )

        elif provider == "ollama":
            from src.llm.ollama_adapter import OllamaAdapter

            self._adapters["ollama"] = OllamaAdapter(
                model=self._config.llm.ollama.model,
                base_url=self._config.llm.ollama.base_url,
                max_tokens=self._config.llm.ollama.max_tokens,
                temperature=self._config.llm.ollama.temperature,
            )

        else:
            providers = ", ".join(SUPPORTED_PROVIDERS)
            raise ValueError(
                f"Unknown provider: '{provider}'. "
                f"Supported providers: {providers}"
            )

    @property
    def current(self) -> LLMAdapter:
        """Get the current active LLM adapter."""
        return self._adapters[self._current_provider]

    @property
    def current_provider_name(self) -> str:
        return self._current_provider

    @property
    def available_providers(self) -> list[str]:
        """Return list of supported provider names."""
        return SUPPORTED_PROVIDERS.copy()

    def switch_provider(self, provider: str) -> str:
        """Switch to a different provider. Returns confirmation message."""
        self._init_provider(provider)
        self._current_provider = provider
        adapter = self._adapters[provider]
        return f"Switched to {provider} ({adapter.model_name})"

    def switch_model(self, model: str, provider: Optional[str] = None) -> str:
        """Switch the model on the current (or specified) provider."""
        target = provider or self._current_provider
        self._init_provider(target)
        adapter = self._adapters[target]
        adapter.model_name = model
        if target != self._current_provider:
            self._current_provider = target
        return f"Model switched to {model} on {target}"

    async def close_all(self) -> None:
        """Close all adapter connections."""
        for adapter in self._adapters.values():
            await adapter.close()
