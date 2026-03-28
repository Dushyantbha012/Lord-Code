from src.llm.groq.base_client import BaseGroqClient

class CompoundClient(BaseGroqClient):
    def __init__(self):
        super().__init__(model="groq/compound")
