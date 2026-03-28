from abc import ABC, abstractmethod
from typing import Generator, List, Dict, Any

class BaseLLM(ABC):
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], 
             stream: bool = True, 
             reasoning: bool = False,
             tools: List[Dict[str, Any]] = None,
             tool_choice: str = "auto") -> Generator[Any, None, None]:
        """
        Send a chat request to the LLM.
        :param messages: List of message dictionaries (role, content).
        :param stream: Whether to stream the response.
        :param reasoning: Whether to enable reasoning mode.
        :param tools: List of tool definitions.
        :param tool_choice: 'auto', 'none', or a specific tool.
        :return: A generator that yields chunks or the full response object.
        """
        pass
