from src.llm.groq.base_client import BaseGroqClient

class GPTOSS120BClient(BaseGroqClient):
    def __init__(self):
        super().__init__(model="openai/gpt-oss-120b")
