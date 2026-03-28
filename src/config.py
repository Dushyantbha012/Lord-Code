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
class OllamaConfig:
    model: str = "llama3.1:8b"
    base_url: str = "http://localhost:11434"
    max_tokens: int = 4096
    temperature: float = 0.0


@dataclass
class LLMConfig:
    default_provider: str = "groq"
    groq: GroqConfig = field(default_factory=GroqConfig)
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


# ---------------------------------------------------------------------------
# Loader helpers
# ---------------------------------------------------------------------------


def _merge_groq(cfg: GroqConfig, data: dict) -> None:
    if "model" in data:
        cfg.model = data["model"]
    if "api_key_env" in data:
        cfg.api_key_env = data["api_key_env"]
    if "max_tokens" in data:
        cfg.max_tokens = int(data["max_tokens"])
    if "temperature" in data:
        cfg.temperature = float(data["temperature"])


def _merge_ollama(cfg: OllamaConfig, data: dict) -> None:
    if "model" in data:
        cfg.model = data["model"]
    if "base_url" in data:
        cfg.base_url = data["base_url"]
    if "max_tokens" in data:
        cfg.max_tokens = int(data["max_tokens"])
    if "temperature" in data:
        cfg.temperature = float(data["temperature"])


def _merge_llm(cfg: LLMConfig, data: dict) -> None:
    if "default_provider" in data:
        cfg.default_provider = data["default_provider"]
    if "groq" in data:
        _merge_groq(cfg.groq, data["groq"])
    if "ollama" in data:
        _merge_ollama(cfg.ollama, data["ollama"])


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
        # Try relative to this source file (for installed packages)
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
        # Set on whichever provider is active
        if cfg.llm.default_provider == "groq":
            cfg.llm.groq.model = os.environ["LORDCODE_MODEL"]
        else:
            cfg.llm.ollama.model = os.environ["LORDCODE_MODEL"]
    if os.environ.get("LORDCODE_MODE"):
        cfg.safety.mode = os.environ["LORDCODE_MODE"]

    # Layer 5: CLI flags (highest priority)
    if provider:
        cfg.llm.default_provider = provider
    if model:
        if cfg.llm.default_provider == "groq":
            cfg.llm.groq.model = model
        else:
            cfg.llm.ollama.model = model
    if mode:
        cfg.safety.mode = mode
    if no_stream:
        cfg.display.stream = False
    cfg.verbose = verbose

    return cfg
