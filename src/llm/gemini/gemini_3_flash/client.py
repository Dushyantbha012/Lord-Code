from src.llm.gemini.base_client import BaseGeminiClient


class Gemini3FlashClient(BaseGeminiClient):
    def __init__(self):
        super().__init__(model="gemini-3-flash-preview")
