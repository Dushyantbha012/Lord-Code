import inspect
from typing import Any, Callable, Dict, List, Optional, Type


class Tool:
    """Represents a tool that can be used by an LLM."""

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable[..., Any],
        parameters: Dict[str, Any],
    ):
        self.name = name
        self.description = description
        self.func = func
        self.parameters = parameters

    def to_dict(self) -> Dict[str, Any]:
        """Convert the tool into a JSON schema dict for the LLM."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __call__(self, *args, **kwargs) -> Any:
        return self.func(*args, **kwargs)


def tool(name: Optional[str] = None, description: Optional[str] = None):
    """Decorator to define a tool from a function."""

    def decorator(func: Callable[..., Any]) -> Tool:
        tool_name = name or func.__name__
        tool_description = description or func.__doc__ or ""
        
        # Simple schema generation from signature
        sig = inspect.signature(func)
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            
            param_type = "string"  # Default
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == bool:
                param_type = "boolean"
            elif param.annotation == List[str]:
                param_type = "array"
                
            properties[param_name] = {"type": param_type}
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
        
        parameters = {
            "type": "object",
            "properties": properties,
            "required": required,
        }
        
        return Tool(tool_name, tool_description, func, parameters)

    return decorator
