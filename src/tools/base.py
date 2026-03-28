"""
Tool system base classes and result types.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    SAFE = "safe"           # read-only operations
    MODERATE = "moderate"   # file writes
    DANGEROUS = "dangerous" # shell commands


@dataclass
class ToolResult:
    """Result returned by a tool execution."""
    success: bool
    output: str              # Full output sent back to the LLM
    display_output: str = "" # Shorter output shown to the user
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.display_output:
            self.display_output = self.output


# ---------------------------------------------------------------------------
# Abstract base tool
# ---------------------------------------------------------------------------


class BaseTool(ABC):
    """Abstract base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Description the LLM reads to decide when to use this tool."""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """JSON Schema for the tool parameters."""
        ...

    @property
    @abstractmethod
    def risk_level(self) -> RiskLevel:
        """How dangerous this tool is."""
        ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with the given arguments."""
        ...

    def get_schema(self) -> dict:
        """Export this tool as an OpenAI/Groq-compatible function schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
