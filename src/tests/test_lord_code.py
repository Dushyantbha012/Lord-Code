import sys
import os
from pathlib import Path

# Adjust path to the project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.agent.agent import CodingAgent

def test_agent_integration():
    """Merged integration tests for the CodingAgent and its tools."""
    agent = CodingAgent()
    
    print("\n[1] --- Testing recursive list_dir ---")
    response = agent.chat("Show me all files in the project recursively.")
    print(f"\nAI Response:\n{response}")

    print("\n[2] --- Testing safe run_command ---")
    response = agent.chat("What is my current user? Use a shell command.")
    print(f"\nAI Response:\n{response}")

    print("\n[3] --- Testing complex multi-step loop ---")
    # Using the user's latest specific request: Create dummy.txt in src/cli and verify
    print("SENDING PROMPT: Create dummy.txt inside src/cli, read it back, and tell me what you read.")
    res = agent.chat("Create a file called dummy.txt containing 'dummy' inside the cli folder in src, read it back to verify, and then tell me what you read.")
    print(f"\nFINAL TEXT RESPONSE:\n{res}")

    print("\n[4] --- Testing shell deletion (requires approval) ---")
    # Cleaning up the test file using a shell command
    print("SENDING PROMPT: Remove src/cli/dummy.txt using a shell command.")
    response = agent.chat("Remove the file src/cli/dummy.txt using a shell command.")
    print(f"\nAI Response:\n{response}")

if __name__ == "__main__":
    # Ensure we have a GROQ_API_KEY for testing
    if not os.getenv("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY not found in environment. Skipping tests.")
    else:
        try:
            test_agent_integration()
        except Exception as e:
            print(f"Tests failed with error: {str(e)}")
