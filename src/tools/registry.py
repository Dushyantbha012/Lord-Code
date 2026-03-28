"""
Tool Registry — Registers tools, dispatches calls, exports schemas.
"""

from __future__ import annotations

import json
from typing import Any

from src.tools.base import BaseTool, ToolResult


class ToolRegistry:
    """Central registry for all tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_tool_names(self) -> list[str]:
        """Get all registered tool names."""
        return list(self._tools.keys())

    def get_schemas(self) -> list[dict]:
        """Export all tool schemas in OpenAI/Groq function-calling format."""
        return [tool.get_schema() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """
        Dispatch execution to the named tool.
        Returns an error ToolResult if the tool doesn't exist or execution fails.
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                output=f"Error: Unknown tool '{name}'. Available tools: {', '.join(self._tools.keys())}",
                display_output=f"❌ Unknown tool: {name}",
            )

        try:
            # Guard: LLM can send null/None arguments (json.loads("null") → None)
            safe_args = arguments if isinstance(arguments, dict) else {}
            return await tool.execute(**safe_args)
        except TypeError as e:
            # Wrong arguments passed
            return ToolResult(
                success=False,
                output=f"Error calling tool '{name}': Invalid arguments — {e}",
                display_output=f"❌ Invalid arguments for {name}: {e}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Error executing tool '{name}': {type(e).__name__}: {e}",
                display_output=f"❌ {name} failed: {e}",
            )
