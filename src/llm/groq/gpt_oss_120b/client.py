from typing import Generator, List, Dict
from groq import Groq
from src.llm.base import BaseLLM
from src.config import Config

class GroqGPTOSS120BClient(BaseLLM):
    def __init__(self):
        self.client = Groq(api_key=Config.GROQ_API_KEY)
        self.model = Config.DEFAULT_MODEL

    def chat(self, messages: List[Dict[str, str]], stream: bool = True, reasoning: bool = False) -> Generator[str, None, None]:
        """
        Send a chat message to Groq.
        If reasoning is True, it adds instruction to the system message or handles reasoning-specific parameters if needed.
        Note: For Groq's reasoning models, specific models like deepseek-r1 are usually used. 
        For gpt-oss-120b, we'll try to emulate reasoning or use model-specific flags if available.
        """
        # Copy messages to avoid mutating the original history
        current_messages = [msg for msg in messages]
        
        if reasoning:
            # If the model does not natively support a 'reasoning' parameter,
            # we can inject a system prompt to encourage step-by-step thinking.
            # Some Groq models might support reasoning_format="raw"
            system_msg = "Please think step by step and provide your reasoning before the final answer."
            if current_messages[0]["role"] == "system":
                current_messages[0]["content"] += f" {system_msg}"
            else:
                current_messages.insert(0, {"role": "system", "content": system_msg})

        params = {
            "model": self.model,
            "messages": current_messages,
            "stream": stream,
        }
        
        # Note: If Groq adds a specific reasoning parameter for this model, 
        # it would be added here.
        
        completion = self.client.chat.completions.create(**params)
        
        if stream:
            for chunk in completion:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        else:
            yield completion.choices[0].message.content
