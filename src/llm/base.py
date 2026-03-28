from abc import ABC, abstractmethod
from typing import Generator, List, Dict, Any

class BaseLLM(ABC):
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], stream: bool = True, reasoning: bool = False) -> Generator[str, None, None]:
        """
        Send a chat request to the LLM.
        :param messages: List of message dictionaries (role, content).
        :param stream: Whether to stream the response.
        :param reasoning: Whether to enable reasoning mode.
        :return: A generator that yields strings (if streaming) or a single string response.
        """
        pass
