"""
Project-specific configuration via .lordcode.yaml
Supports custom instructions, ignored paths, preferred tools, model overrides, and token budgets.
"""

import os
from typing import List, Dict, Optional, Any

class ProjectConfig:
    """Loads and provides access to project-specific .lordcode.yaml configuration."""

    DEFAULT_IGNORED_PATHS = [
        "venv/", ".venv/", "node_modules/", "__pycache__/",
        ".git/", ".idea/", ".vscode/", "*.pyc", "*.pyo",
        "dist/", "build/", ".eggs/", "*.egg-info/",
        ".tox/", ".mypy_cache/", ".pytest_cache/",
        "target/",  # Rust/Java
        ".lord-code/",  # Lord Code data directory
    ]

    DEFAULT_KEY_FILES = [
        "README.md", "readme.md", "README.rst",
        "package.json", "package-lock.json",
        "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile",
        "Cargo.toml", "go.mod", "go.sum",
        "Makefile", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
        ".env.example", "tsconfig.json", "webpack.config.js", "vite.config.ts",
        "Gemfile", "pom.xml", "build.gradle",
    ]

    def __init__(self):
        self.custom_instructions: str = ""
        self.ignored_paths: List[str] = list(self.DEFAULT_IGNORED_PATHS)
        self.preferred_tools: List[str] = []
        self.model: Optional[str] = None
        self.token_budget: Dict[str, Any] = {
            "system_prompt": 2500,
            "file_contents": 5000,
            "conversation": "auto",
        }
        self.key_files: List[str] = list(self.DEFAULT_KEY_FILES)
        self._raw: Dict = {}

    @classmethod
    def load(cls, root_dir: str) -> "ProjectConfig":
        """Load configuration from .lordcode.yaml in the given directory.
        Falls back to defaults if no config file is found."""
        config = cls()
        
        yaml_path = os.path.join(root_dir, ".lordcode.yaml")
        yml_path = os.path.join(root_dir, ".lordcode.yml")
        
        config_path = None
        if os.path.isfile(yaml_path):
            config_path = yaml_path
        elif os.path.isfile(yml_path):
            config_path = yml_path
        
        if config_path is None:
            return config  # Return defaults

        try:
            import yaml
            with open(config_path, "r") as f:
                data = yaml.safe_load(f) or {}
            config._raw = data
            config._apply(data)
        except ImportError:
            pass  # pyyaml not installed, use defaults
        except Exception:
            pass  # Malformed config, use defaults
        
        return config

    def _apply(self, data: Dict):
        """Apply parsed YAML data to config fields."""
        if "custom_instructions" in data and isinstance(data["custom_instructions"], str):
            self.custom_instructions = data["custom_instructions"].strip()
        
        if "ignored_paths" in data and isinstance(data["ignored_paths"], list):
            # Merge with defaults (user additions)
            extra = [p for p in data["ignored_paths"] if p not in self.ignored_paths]
            self.ignored_paths.extend(extra)
        
        if "preferred_tools" in data and isinstance(data["preferred_tools"], list):
            self.preferred_tools = data["preferred_tools"]
        
        if "model" in data and isinstance(data["model"], str):
            self.model = data["model"]
        
        if "token_budget" in data and isinstance(data["token_budget"], dict):
            for key in ("system_prompt", "file_contents", "conversation"):
                if key in data["token_budget"]:
                    self.token_budget[key] = data["token_budget"][key]
        
        if "key_files" in data and isinstance(data["key_files"], list):
            extra = [f for f in data["key_files"] if f not in self.key_files]
            self.key_files.extend(extra)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize config to a dict (used by config snapshots)."""
        data = {}
        if self.custom_instructions:
            data["custom_instructions"] = self.custom_instructions
        if self.model:
            data["model"] = self.model
        if self.token_budget:
            data["token_budget"] = dict(self.token_budget)
        if self.preferred_tools:
            data["preferred_tools"] = list(self.preferred_tools)

        # Only include non-default ignored paths
        custom_ignored = [p for p in self.ignored_paths if p not in self.DEFAULT_IGNORED_PATHS]
        if custom_ignored:
            data["ignored_paths"] = custom_ignored

        # Only include non-default key files
        custom_keys = [f for f in self.key_files if f not in self.DEFAULT_KEY_FILES]
        if custom_keys:
            data["key_files"] = custom_keys

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectConfig":
        """Deserialize a config from a dict (used by config snapshot restore)."""
        config = cls()
        config._apply(data)
        return config

    def __repr__(self):
        return (
            f"ProjectConfig(model={self.model}, "
            f"custom_instructions={'yes' if self.custom_instructions else 'none'}, "
            f"ignored={len(self.ignored_paths)} patterns, "
            f"budget={self.token_budget})"
        )
