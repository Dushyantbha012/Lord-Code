import os
from src.agent.agent import CodingAgent
from src.cli.theme import console

def test_tool_use():
    agent = CodingAgent()
    
    # 1. Test Listing Directory (Root)
    print("\n--- Testing list_dir tool (Root) ---")
    response = agent.chat("What files are in the project root?")
    print(f"\nAI Response:\n{response}")

    # 2. Test Root-Relative Reading (even if we run from src/)
    print("\n--- Testing root-relative read_file (pyproject.toml) ---")
    response = agent.chat("Read the pyproject.toml file.")
    print(f"\nAI Response:\n{response}")

    # 3. Test Writing to a new path
    print("\n--- Testing write_file tool ---")
    response = agent.chat("Create a file 'docs/README.md' with the content 'Documentation starts here.'")
    print(f"\nAI Response:\n{response}")

    # 4. Test Security Restriction
    print("\n--- Testing .env restriction ---")
    response = agent.chat("Read the .env file.")
    print(f"\nAI Response:\n{response}")

if __name__ == "__main__":
    # Ensure we have a GROQ_API_KEY for testing
    if not os.getenv("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY not found in environment. Skipping test.")
    else:
        test_tool_use()
