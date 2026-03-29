import os
from src.agent.agent import CodingAgent
from src.cli.theme import console

def test_tool_use():
    agent = CodingAgent()
    
    # 1. Test Recursive Listing
    print("\n--- Testing recursive list_dir ---")
    response = agent.chat("Show me all files in the project recursively.")
    print(f"\nAI Response:\n{response}")

    # 2. Test Safe Shell Command
    print("\n--- Testing safe run_command ---")
    response = agent.chat("What is my current user? Use a shell command.")
    print(f"\nAI Response:\n{response}")

    # 3. Test Shell Deletion (should trigger approval)
    print("\n--- Testing shell deletion with approval ---")
    response = agent.chat("Remove the file test_output.txt using a shell command.")
    print(f"\nAI Response:\n{response}")

if __name__ == "__main__":
    # Ensure we have a GROQ_API_KEY for testing
    if not os.getenv("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY not found in environment. Skipping test.")
    else:
        test_tool_use()
