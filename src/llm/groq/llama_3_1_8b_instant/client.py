from src.llm.groq.base_client import BaseGroqClient

class Llama31_8B_InstantClient(BaseGroqClient):
    def __init__(self):
        super().__init__(model="llama-3.1-8b-instant")
