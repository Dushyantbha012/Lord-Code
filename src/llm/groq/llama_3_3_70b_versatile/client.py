from src.llm.groq.base_client import BaseGroqClient

class Llama33_70B_VersatileClient(BaseGroqClient):
    def __init__(self):
        super().__init__(model="llama-3.3-70b-versatile")
