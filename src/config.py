import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

APP_NAME = "Lord Code"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = "AI Coding Agent"

# LLM Configuration
# Use gpt-oss-20b as requested
DEFAULT_MODEL = "openai/gpt-oss-20b"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# TODO: Add multi-modal support.
# TODO: Integrate Qdrant vector database for chat memory in the future.

# Slash commands that exit the REPL
EXIT_COMMANDS = {"/exit", "/quit"}

# All recognized slash commands
SLASH_COMMANDS = {
    "/exit": "Exit Lord Code",
    "/quit": "Exit Lord Code",
    "/help": "Show available commands",
    "/clear": "Clear the screen",
    "/version": "Show version information",
}
