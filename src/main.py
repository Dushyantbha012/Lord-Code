import sys
import os

# Add src to python path if needed (though running from root should work)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config
from src.llm.groq.gpt_oss_120b.client import GroqGPTOSS120BClient
from src.cli.chat_loop import ChatLoop

def main():
    if not Config.validate():
        sys.exit(1)
        
    llm = GroqGPTOSS120BClient()
    chat = ChatLoop(llm)
    chat.run()

if __name__ == "__main__":
    main()
