"""
Lord-Code Configuration System.

Loads config from: defaults → default_config.toml → .lordcode.toml → env vars → CLI flags.
"""

from __future__ import annotations

import os
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Supported providers list
# ---------------------------------------------------------------------------

SUPPORTED_PROVIDERS = ["groq", "openai", "anthropic", "gemini", "ollama"]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class GroqConfig:
    model: str = "llama-3.3-70b-versatile"
    api_key_env: str = "GROQ_API_KEY"
    max_tokens: int = 4096
    temperature: float = 0.0

    @property
    def api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env)


@dataclass
class OpenAIConfig:
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    max_tokens: int = 4096
    temperature: float = 0.0

    @property
    def api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env)


@dataclass
class AnthropicConfig:
    model: str = "claude-sonnet-4-20250514"
    api_key_env: str = "ANTHROPIC_API_KEY"
    max_tokens: int = 4096
    temperature: float = 0.0

    @property
    def api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env)


@dataclass
class GeminiConfig:
    model: str = "gemini-2.0-flash"
    api_key_env: str = "GEMINI_API_KEY"
    max_tokens: int = 4096
    temperature: float = 0.0

    @property
    def api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env)


@dataclass
class OllamaConfig:
    model: str = "llama3.1:8b"
    base_url: str = "http://localhost:11434"
    max_tokens: int = 4096
    temperature: float = 0.0


@dataclass
class LLMConfig:
    default_provider: str = "groq"
    groq: GroqConfig = field(default_factory=GroqConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = field(default_factory=AnthropicConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)


@dataclass
class SafetyConfig:
    mode: str = "smart"  # paranoid | smart | yolo
    max_loop_iterations: int = 25
    command_timeout_seconds: int = 30


@dataclass
class DisplayConfig:
    stream: bool = True
    show_tool_calls: bool = True
    show_token_usage: bool = True
    theme: str = "monokai"


@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)

    # Runtime overrides (set via CLI flags, not persisted)
    verbose: bool = False
    working_directory: str = field(default_factory=lambda: os.getcwd())
    session_id: str = ""


# ---------------------------------------------------------------------------
# Loader helpers
# ---------------------------------------------------------------------------


def _merge_provider_config(cfg, data: dict) -> None:
    """Generic merge for any provider config with standard fields."""
    if "model" in data:
        cfg.model = data["model"]
    if "api_key_env" in data:
        cfg.api_key_env = data["api_key_env"]
    if "max_tokens" in data:
        cfg.max_tokens = int(data["max_tokens"])
    if "temperature" in data:
        cfg.temperature = float(data["temperature"])
    if "base_url" in data and hasattr(cfg, "base_url"):
        cfg.base_url = data["base_url"]


def _merge_llm(cfg: LLMConfig, data: dict) -> None:
    if "default_provider" in data:
        cfg.default_provider = data["default_provider"]
    for provider in SUPPORTED_PROVIDERS:
        if provider in data and hasattr(cfg, provider):
            _merge_provider_config(getattr(cfg, provider), data[provider])


def _merge_safety(cfg: SafetyConfig, data: dict) -> None:
    if "mode" in data:
        cfg.mode = data["mode"]
    if "max_loop_iterations" in data:
        cfg.max_loop_iterations = int(data["max_loop_iterations"])
    if "command_timeout_seconds" in data:
        cfg.command_timeout_seconds = int(data["command_timeout_seconds"])


def _merge_display(cfg: DisplayConfig, data: dict) -> None:
    if "stream" in data:
        cfg.stream = bool(data["stream"])
    if "show_tool_calls" in data:
        cfg.show_tool_calls = bool(data["show_tool_calls"])
    if "show_token_usage" in data:
        cfg.show_token_usage = bool(data["show_token_usage"])
    if "theme" in data:
        cfg.theme = data["theme"]


def _merge_toml(cfg: Config, data: dict) -> None:
    """Merge a parsed TOML dict into the Config object."""
    if "llm" in data:
        _merge_llm(cfg.llm, data["llm"])
    if "safety" in data:
        _merge_safety(cfg.safety, data["safety"])
    if "display" in data:
        _merge_display(cfg.display, data["display"])


def _load_toml_file(path: Path) -> dict:
    """Load a TOML file and return its contents as a dict."""
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def _get_provider_config(cfg: Config, provider: str):
    """Get the config object for a given provider name."""
    return getattr(cfg.llm, provider, None)


def _set_model_for_provider(cfg: Config, provider: str, model: str) -> None:
    """Set the model on the given provider config."""
    pcfg = _get_provider_config(cfg, provider)
    if pcfg:
        pcfg.model = model


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    mode: Optional[str] = None,
    no_stream: bool = False,
    verbose: bool = False,
) -> Config:
    """
    Load configuration with full precedence chain:
    defaults → default_config.toml → .lordcode.toml → env vars → CLI flags
    """
    # Load .env file
    load_dotenv()

    # Start with defaults
    cfg = Config()

    # Layer 1: default_config.toml (shipped with the project)
    project_root = Path(cfg.working_directory)
    default_toml = project_root / "default_config.toml"
    if not default_toml.exists():
        default_toml = Path(__file__).parent.parent / "default_config.toml"
    _merge_toml(cfg, _load_toml_file(default_toml))

    # Layer 2: .lordcode.toml in the current project
    project_toml = project_root / ".lordcode.toml"
    _merge_toml(cfg, _load_toml_file(project_toml))

    # Layer 3: Global config in ~/.config/lordcode/config.toml
    global_toml = Path.home() / ".config" / "lordcode" / "config.toml"
    _merge_toml(cfg, _load_toml_file(global_toml))

    # Layer 4: Environment variables
    if os.environ.get("LORDCODE_PROVIDER"):
        cfg.llm.default_provider = os.environ["LORDCODE_PROVIDER"]
    if os.environ.get("LORDCODE_MODEL"):
        _set_model_for_provider(cfg, cfg.llm.default_provider, os.environ["LORDCODE_MODEL"])
    if os.environ.get("LORDCODE_MODE"):
        cfg.safety.mode = os.environ["LORDCODE_MODE"]

    # Layer 5: CLI flags (highest priority)
    if provider:
        cfg.llm.default_provider = provider
    if model:
        _set_model_for_provider(cfg, cfg.llm.default_provider, model)
    if mode:
        cfg.safety.mode = mode
    if no_stream:
        cfg.display.stream = False
    cfg.verbose = verbose

    return cfg
