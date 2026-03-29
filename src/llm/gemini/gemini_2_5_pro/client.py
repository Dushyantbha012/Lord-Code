from src.llm.gemini.base_client import BaseGeminiClient


class Gemini25ProClient(BaseGeminiClient):
    def __init__(self):
        super().__init__(model="gemini-2.5-pro-preview-06-2025")
