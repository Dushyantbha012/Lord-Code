from typing import List, Dict, Optional, Any
from groq import Groq
from src.config import GROQ_API_KEY, DEFAULT_MODEL

class GroqClient:
    """Client for interacting with the Groq API."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or GROQ_API_KEY
        self.model = model
        
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set. Please provide it in your .env file.")
            
        self.client = Groq(api_key=self.api_key)

    def get_chat_completion(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        """Fetch a chat completion from the Groq API with tool support."""
        try:
            kwargs = {
                "messages": messages,
                "model": self.model,
            }
            if tools:
                # Filter to match Groq's tool format (wrapping in type: function)
                kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
                kwargs["tool_choice"] = "auto"
                
            chat_completion = self.client.chat.completions.create(**kwargs)
            return chat_completion, getattr(chat_completion, "usage", None)
        except Exception as e:
            # We'll handle errors in the agent layer
            raise e
