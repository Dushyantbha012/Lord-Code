import os
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"))

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    DEFAULT_MODEL = "openai/gpt-oss-120b"
    
    AVAILABLE_MODELS = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "groq/compound",
        "groq/compound-mini"
    ]
    
    # Models that support reasoning (either natively or via prompt engineering)
    REASONING_MODELS = [
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "groq/compound",
        "groq/compound-mini"
    ]
    
    REASONING_MODEL_SUFFIX = "-reasoning"
    
    @classmethod
    def validate(cls):
        from rich.console import Console
        console = Console()
        if not cls.GROQ_API_KEY:
            console.print("[bold red]Error: GROQ_API_KEY not found in environment variables.[/bold red]")
            console.print("Please create a .env file in the project root with [yellow]GROQ_API_KEY=your_key_here[/yellow]")
            return False
        return True
