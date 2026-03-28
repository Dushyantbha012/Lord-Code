"""Tests for the configuration system."""

import os
import pytest
from pathlib import Path

from src.config import load_config, Config


class TestConfigDefaults:
    """Test default configuration values."""

    def test_default_provider(self):
        cfg = Config()
        assert cfg.llm.default_provider == "groq"

    def test_default_safety_mode(self):
        cfg = Config()
        assert cfg.safety.mode == "smart"

    def test_default_stream(self):
        cfg = Config()
        assert cfg.display.stream is True

    def test_default_max_iterations(self):
        cfg = Config()
        assert cfg.safety.max_loop_iterations == 25


class TestConfigLoading:
    """Test config loading with various overrides."""

    def test_cli_provider_override(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        cfg = load_config(provider="ollama")
        assert cfg.llm.default_provider == "ollama"

    def test_cli_mode_override(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        cfg = load_config(mode="yolo")
        assert cfg.safety.mode == "yolo"

    def test_cli_no_stream(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        cfg = load_config(no_stream=True)
        assert cfg.display.stream is False

    def test_cli_verbose(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        cfg = load_config(verbose=True)
        assert cfg.verbose is True

    def test_env_var_provider(self, monkeypatch):
        monkeypatch.setenv("LORDCODE_PROVIDER", "ollama")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        cfg = load_config()
        assert cfg.llm.default_provider == "ollama"

    def test_env_var_mode(self, monkeypatch):
        monkeypatch.setenv("LORDCODE_MODE", "paranoid")
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        cfg = load_config()
        assert cfg.safety.mode == "paranoid"


class TestGroqConfig:
    """Test Groq-specific config."""

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-api-key-123")
        cfg = Config()
        assert cfg.llm.groq.api_key == "test-api-key-123"

    def test_api_key_missing(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        cfg = Config()
        assert cfg.llm.groq.api_key is None

    def test_default_model(self):
        cfg = Config()
        assert cfg.llm.groq.model == "llama-3.3-70b-versatile"
