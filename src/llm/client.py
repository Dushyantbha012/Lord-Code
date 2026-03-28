from typing import List, Dict, Optional
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

    def get_chat_completion(self, messages: List[Dict[str, str]]) -> str:
        """Fetch a chat completion from the Groq API."""
        try:
            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
            )
            return chat_completion.choices[0].message.content or ""
        except Exception as e:
            return f"Error: Failed to get response from Groq. {str(e)}"
