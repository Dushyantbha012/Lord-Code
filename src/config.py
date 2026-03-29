import os
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"))

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    DEFAULT_MODEL = "openai/gpt-oss-120b"
    
    AVAILABLE_MODELS = [
        # ── Groq ──
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "groq/compound",
        "groq/compound-mini",
        # ── Gemini ──
        "gemini/2.5-pro",
        "gemini/2.5-flash",
        "gemini/2.5-flash-lite",
        "gemini/3-flash",
    ]
    
    # Models that support reasoning (either natively or via prompt engineering)
    REASONING_MODELS = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "groq/compound",
        "groq/compound-mini",
        # Gemini models support reasoning natively
        "gemini/2.5-pro",
        "gemini/2.5-flash",
        "gemini/3-flash",
    ]
    
    REASONING_MODEL_SUFFIX = "-reasoning"

    # ── Context Window Limits (per model) ──
    MODEL_CONTEXT_LIMITS = {
        # Groq
        "openai/gpt-oss-120b": 128_000,
        "openai/gpt-oss-20b": 128_000,
        "llama-3.3-70b-versatile": 131_072,
        "llama-3.1-8b-instant": 131_072,
        "groq/compound": 131_072,
        "groq/compound-mini": 131_072,
        # Gemini
        "gemini/2.5-pro": 1_048_576,
        "gemini/2.5-flash": 1_048_576,
        "gemini/2.5-flash-lite": 1_048_576,
        "gemini/3-flash": 1_048_576,
    }

    # ── Default Token Budget ──
    DEFAULT_TOKEN_BUDGET = {
        "system_prompt": 2500,
        "file_contents": 5000,
        "conversation": "auto",  # auto = context_limit - system - files - 4096 headroom
    }

    @classmethod
    def validate(cls):
        from rich.console import Console
        console = Console()
        if not cls.GROQ_API_KEY and not cls.GEMINI_API_KEY:
            console.print("[bold red]Error: No API key found.[/bold red]")
            console.print("Please add at least one to your .env file:")
            console.print("  [yellow]GROQ_API_KEY=your_groq_key[/yellow]")
            console.print("  [yellow]GEMINI_API_KEY=your_gemini_key[/yellow]")
            return False
        return True

