from typing import Generator, List, Dict
from groq import Groq
from src.llm.base import BaseLLM
from src.config import Config

class GroqGPTOSS120BClient(BaseLLM):
    def __init__(self):
        self.client = Groq(api_key=Config.GROQ_API_KEY)
        self.model = Config.DEFAULT_MODEL

    def chat(self, messages: List[Dict[str, str]], 
             stream: bool = True, 
             reasoning: bool = False,
             tools: List[Dict[str, Any]] = None,
             tool_choice: str = "auto") -> Generator[Any, None, None]:
        # Copy messages to avoid mutating the original history
        current_messages = [msg for msg in messages]
        
        if reasoning:
            system_msg = "Please think step by step and provide your reasoning before the final answer."
            if current_messages and current_messages[0]["role"] == "system":
                current_messages[0]["content"] += f" {system_msg}"
            else:
                current_messages.insert(0, {"role": "system", "content": system_msg})

        params = {
            "model": self.model,
            "messages": current_messages,
            "stream": stream,
        }
        
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice
            # Note: Groq might have specific behaviors for streaming tool calls.
            # Some SDK versions might require stream=False for tool use or specific handling.
            # We'll allow streaming but handle the possibility of tool calls in chunks.

        if stream:
            # We enable stream_options to get usage in the last chunk
            params["stream_options"] = {"include_usage": True}
            completion = self.client.chat.completions.create(**params)
            for chunk in completion:
                yield chunk
        else:
            completion = self.client.chat.completions.create(**params)
            yield completion
