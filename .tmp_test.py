import os
from src.llm.gemini.base_client import BaseGeminiClient
import json

os.environ["GEMINI_API_KEY"] = "dummy_key"
client = BaseGeminiClient("gemini/2.5-pro")

messages = [
    {"role": "system", "content": "You are a bot"},
    {"role": "user", "content": "Hello"}
]

try:
    # We expect an auth error from Google, but the message parsing should work
    gen = client.chat(messages, stream=True)
    next(gen)
except Exception as e:
    print(f"Exception: {type(e).__name__}: {e}")
