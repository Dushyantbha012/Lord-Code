"""
Gemini LLM Factory.

Maps user-facing model IDs (prefixed with 'gemini/') to concrete client classes.
"""

from src.llm.gemini.gemini_2_5_pro.client import Gemini25ProClient
from src.llm.gemini.gemini_2_5_flash.client import Gemini25FlashClient
from src.llm.gemini.gemini_2_5_flash_lite.client import Gemini25FlashLiteClient
from src.llm.gemini.gemini_3_flash.client import Gemini3FlashClient


GEMINI_MODEL_MAP = {
    "gemini/2.5-pro": Gemini25ProClient,
    "gemini/2.5-flash": Gemini25FlashClient,
    "gemini/2.5-flash-lite": Gemini25FlashLiteClient,
    "gemini/3-flash": Gemini3FlashClient,
}


def get_gemini_client(model_id: str):
    """
    Get a Gemini LLM client by model ID.

    Args:
        model_id: One of 'gemini/2.5-pro', 'gemini/2.5-flash', 
                  'gemini/2.5-flash-lite', 'gemini/3-flash'
    
    Returns:
        A BaseGeminiClient subclass instance

    Raises:
        ValueError: If model_id is not recognized
    """
    client_class = GEMINI_MODEL_MAP.get(model_id)
    if not client_class:
        available = ", ".join(sorted(GEMINI_MODEL_MAP.keys()))
        raise ValueError(
            f"No Gemini client for model: {model_id}. "
            f"Available: {available}"
        )
    return client_class()
