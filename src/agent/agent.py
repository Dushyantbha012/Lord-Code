from typing import List, Dict
from src.llm.client import GroqClient

class CodingAgent:
    """Agent that handles coding tasks using the Groq LLM."""

    def __init__(self, system_prompt: str = "You are a helpful AI coding assistant."):
        self.client = GroqClient()
        self.system_prompt = system_prompt
        self.messages: List[Dict[str, str]] = [
            {"role": "system", "content": self.system_prompt}
        ]

    def chat(self, user_input: str) -> str:
        """Process user input and return AI response with chat history."""
        # 1. Add user message to history
        self.messages.append({"role": "user", "content": user_input})

        # 2. Get response from LLM
        response = self.client.get_chat_completion(self.messages)

        # 3. Add AI response to history (only if it's not an error)
        if not response.startswith("Error:"):
            self.messages.append({"role": "assistant", "content": response})
        
        # NOTE: In the future, we'll use Qdrant for persistent chat memory.
        return response

    def clear_history(self) -> None:
        """Reset the chat history."""
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
