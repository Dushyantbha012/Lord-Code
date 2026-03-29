import json
from typing import Any, Dict, List, Optional
from src.tools.base import Tool


class ToolManager:
    """Manages tool registration and execution."""

    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        """Add a tool to the registry."""
        self.tools[tool.name] = tool

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return all tools as JSON schemas for the LLM."""
        return [tool.to_dict()["function"] for tool in self.tools.values()]

    def execute_tool(self, name: str, arguments: str) -> str:
        """Parse arguments and execute the tool."""
        if name not in self.tools:
            return f"Error: Tool '{name}' not found."

        try:
            # Parse arguments (LLMs return them as a JSON string)
            args = json.loads(arguments)
            tool = self.tools[name]
            
            # Execute the tool and return the output
            return str(tool(**args))
        except Exception as e:
            return f"Error: Failed to execute tool '{name}'. {str(e)}"

# Singleton instance for easy access
tool_manager = ToolManager()

# Automatically register tools
from src.tools.file_ops import read_file, write_file, list_dir
from src.tools.shell import run_command

tool_manager.register(read_file)
tool_manager.register(write_file)
tool_manager.register(list_dir)
tool_manager.register(run_command)
