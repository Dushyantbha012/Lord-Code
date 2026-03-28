"""
Provider Manager — Holds LLM adapters and supports runtime switching.
"""

from __future__ import annotations

from typing import Optional

from src.config import Config
from src.llm.base import LLMAdapter
from src.llm.groq_adapter import GroqAdapter
from src.llm.ollama_adapter import OllamaAdapter


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
        elif provider == "ollama":
            self._adapters["ollama"] = OllamaAdapter(
                model=self._config.llm.ollama.model,
                base_url=self._config.llm.ollama.base_url,
                max_tokens=self._config.llm.ollama.max_tokens,
                temperature=self._config.llm.ollama.temperature,
            )
        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'groq' or 'ollama'.")

    @property
    def current(self) -> LLMAdapter:
        """Get the current active LLM adapter."""
        return self._adapters[self._current_provider]

    @property
    def current_provider_name(self) -> str:
        return self._current_provider

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
