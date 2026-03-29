from src.llm.groq.gpt_oss_120b.client import GPTOSS120BClient
from src.llm.groq.gpt_oss_20b.client import GPTOSS20BClient
from src.llm.groq.llama_3_3_70b_versatile.client import Llama33_70B_VersatileClient
from src.llm.groq.llama_3_1_8b_instant.client import Llama31_8B_InstantClient
from src.llm.groq.compound.client import CompoundClient
from src.llm.groq.compound_mini.client import CompoundMiniClient

def get_llm_client(model_id: str):
    # ── Gemini models (delegated to Gemini factory) ──
    if model_id.startswith("gemini/"):
        from src.llm.gemini.factory import get_gemini_client
        return get_gemini_client(model_id)

    # ── Groq models ──
    mapping = {
        "openai/gpt-oss-120b": GPTOSS120BClient,
        "openai/gpt-oss-20b": GPTOSS20BClient,
        "llama-3.3-70b-versatile": Llama33_70B_VersatileClient,
        "llama-3.1-8b-instant": Llama31_8B_InstantClient,
        "groq/compound": CompoundClient,
        "groq/compound-mini": CompoundMiniClient
    }
    
    client_class = mapping.get(model_id)
    if not client_class:
        raise ValueError(f"No client found for model: {model_id}")
    
    return client_class()

