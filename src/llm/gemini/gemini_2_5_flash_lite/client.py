from src.llm.gemini.base_client import BaseGeminiClient


class Gemini25FlashLiteClient(BaseGeminiClient):
    def __init__(self):
        super().__init__(model="gemini-2.5-flash-lite")
