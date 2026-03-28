from typing import Generator, List, Dict, Any
from groq import Groq
from src.llm.base import BaseLLM
from src.config import Config

class BaseGroqClient(BaseLLM):
    def __init__(self, model: str):
        self.client = Groq(api_key=Config.GROQ_API_KEY)
        self.model = model

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
            "max_completion_tokens": 4096,  # Default limit for safety
        }
        
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        if stream:
            completion = self.client.chat.completions.create(**params)
            for chunk in completion:
                yield chunk
        else:
            completion = self.client.chat.completions.create(**params)
            yield completion
