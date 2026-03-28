import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    DEFAULT_MODEL = "openai/gpt-oss-120b"
    REASONING_MODEL_SUFFIX = "-reasoning"  # Placeholder if reasoning uses a different name or param
    
    @classmethod
    def validate(cls):
        if not cls.GROQ_API_KEY:
            print("Error: GROQ_API_KEY not found in environment variables.")
            print("Please create a .env file with GROQ_API_KEY=your_key_here")
            return False
        return True
