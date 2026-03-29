# Lord Code ✴

Lord Code is a professional AI Coding Agent CLI designed with a minimalist, high-end aesthetic inspired by modern agentic tools like Claude Code. It features an autonomous agentic loop, a robust tool system, and strict safety guardrails.

## 🚀 Features

- **Autonomous Agentic Loop**: A ReAct-style loop that handles thinking, tool calling, and observing until a task is completed.
- **Powered by Groq**: High-speed LLM integration with multi-turn conversation memory.
- **Advanced Tool Suite**:
    - **File Operations**: Read, write, and list (recursive tree-view) files.
    - **Shell Execution**: Run commands directly in the project root.
- **Safety Guardrails**:
    - **Project Sandboxing**: Restricts all operations to the project root directory.
    - **Command Blacklist**: Blocks dangerous system commands (e.g., `rm -rf /`).
    - **Risk-Based Confirmations**: Mandatory user approval for destructive actions (writing files, deleting, etc.).
- **Resource Tracking**: Real-time token usage reporting (prompt, completion, and total) for every request.
- **Premium UI/UX**: Rich Markdown rendering, terminal previews, and status indicators.

## 🚀 Getting Started

### Prerequisites
- **Python 3.9+**
- A Groq API Key (Set in your `.env` file)

### 1. Installation
Clone the repository and install the project in editable mode:

```bash
# Clone the repository
git clone https://github.com/Dushyantbha012/Lord-Code.git
cd Lord-Code

# Install dependencies and CLI
pip install -e .
```

### 2. Configuration
Create a `.env` file in the root directory and add your Groq API key:

```env
GROQ_API_KEY=your_api_key_here
```

### 3. Run the Application
Start Lord Code using the following command:

```bash
lord-code
```

---

## 🛠 Commands

Type these commands directly into the prompt:

| Command | Description |
| :--- | :--- |
| `/help` | List all available slash commands |
| `/clear` | Clear the terminal and reset the banner |
| `/version` | Display current version information |
| `/exit`, `/quit` | Gracefully exit the session |

---

## 📁 File Structure & Working

### Core Logic
- **`src/main.py`**: The main entry point. Initializes the `CLIApp` and starts the REPL loop.
- **`src/agent/agent.py`**: Contains the `CodingAgent`. This is the brain of the CLI, orchestrating the multi-turn "Thinking... Acting... Observing" loop.
- **`src/llm/client.py`**: Manages the connection to Groq's API, handles tool schemas, and tracks token usage.

### Tool System
- **`src/tools/manager.py`**: The `ToolManager` registers and coordinates the execution of all available tools.
- **`src/tools/base.py`**: Defines the `@tool` decorator used to turn regular functions into LLM-compatible tool definitions.
- **`src/tools/file_ops.py`**: Implements file system interactions (`read_file`, `write_file`, `list_dir` with tree-view).
- **`src/tools/shell.py`**: Implements the `run_command` tool for shell execution.

### Safety & Utilities
- **`src/safety/guardrail.py`**: The `SafetyGuard` class. It centerally validates file paths (sandboxing) and shell commands (blacklist/risk assessment).
- **`src/tools/utils.py`**: Contains helper functions like `find_project_root` to ensure paths are always relative to the project directory.

### UI & UX
- **`src/cli/app.py`**: The `CLIApp` class. Manages the REPL (Read-Eval-Print Loop), routes slash commands, and integrates the AI agent.
- **`src/cli/theme.py`**: Uses `Rich` to provide beautiful formatting, panels, terminal previews, and status indicators.
- **`src/cli/prompt.py`**: Configures the `prompt_toolkit` session for a smooth interactive typing experience.

### Testing
- **`src/tests/test_lord_code.py`**: A unified integration test suite that verifies tool execution, safety guardrails, and agent reasoning.

---

## 🎨 UI/UX Features

- **Premium Splash Screen**: A bold, Coral-themed startup UI with a custom block-style logo.
- **Terminal Previews**: See exactly what command the AI wants to run before you approve it.
- **Resource Footer**: Subtle token usage reports after every AI response.

---
