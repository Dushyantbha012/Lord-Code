"""Tools package — registers all available tools."""

from src.tools.base import BaseTool, RiskLevel, ToolResult
from src.tools.registry import ToolRegistry
from src.tools.read_file import ReadFileTool
from src.tools.write_file import WriteFileTool
from src.tools.list_directory import ListDirectoryTool
from src.tools.run_command import RunCommandTool


def create_tool_registry(working_dir: str, command_timeout: int = 30) -> ToolRegistry:
    """Create and populate the tool registry with all available tools."""
    registry = ToolRegistry()
    registry.register(ReadFileTool(working_dir))
    registry.register(WriteFileTool(working_dir))
    registry.register(ListDirectoryTool(working_dir))
    registry.register(RunCommandTool(working_dir, timeout=command_timeout))
    return registry


__all__ = [
    "BaseTool",
    "RiskLevel",
    "ToolResult",
    "ToolRegistry",
    "create_tool_registry",
]
