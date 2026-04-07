# Lord Code ✴

Lord Code is a professional AI Coding Agent CLI designed with a minimalist, high-end aesthetic inspired by modern agentic tools like Claude Code. It features an autonomous agentic loop, a robust tool system, and a sophisticated layered context management system.

## 🚀 Features

- **Autonomous Agentic Loop**: A ReAct-style loop that handles thinking, tool calling, and observing until a task is completed.
- **Layered Context System**:
    - **Global Context (`lord_code.md`)**: A root-level "Source of Truth" for your project (e.g., coding standards, library preferences).
    - **Modular Context (`.context.md`)**: Directory-specific instructions that apply only to the current working module.
    - **Persistent Memory**: The agent "remembers" facts and preferences across sessions via a local memory store.
- **Advanced Tool Suite**:
    - **File Operations**: Read, write, and list (recursive tree-view) files.
    - **Shell Execution**: Run commands directly in the project root with safety guardrails.
    - **Memory Tools**: `remember` and `recall` tools for managing persistent knowledge.
- **Safety Guardrails**:
    - **Project Sandboxing**: Restricts all operations to the project root directory.
    - **Command Blacklist**: Blocks dangerous system commands (e.g., `rm -rf /`).
    - **Risk-Based Confirmations**: Mandatory user approval for destructive actions.
- **Resource Tracking**: Real-time token usage reporting (prompt, completion, and total).
- **Premium UI/UX**: Rich Markdown rendering, terminal previews, and status indicators.

## 🚀 Getting Started

### Prerequisites
- **Python 3.9+**
- A Groq API Key (Set in your `.env` file)

### 1. Installation
Clone the repository and install the project in editable mode:

```bash
pip install -e .
```

### 2. Configuration
Create a `.env` file in the root directory and add your Groq API key:

```env
GROQ_API_KEY=your_api_key_here
```

### 3. Run the Application
Start Lord Code:

```bash
lord-code
```

---

## 🧠 Context Management Best Practices

To get the most out of Lord Code, follow these strategies for managing the agent's knowledge:

### 1. The "Source of Truth" (`lord_code.md`)
Create a `lord_code.md` in your project root to define global rules. 
*Example Contents:*
- "We use FastAPI for the backend."
- "All frontend components must be in TypeScript."
- "Indent with 4 spaces, no tabs."

### 2. Modular Context (`.context.md`)
For complex sub-directories, place a `.context.md` file inside them. The agent will read these only when working in those specific areas.
*Example:* A `src/auth/.context.md` might contain:
- "Always check JWT validation in every endpoint."
- "The database schema for 'users' is defined in `models.py`."

### 3. Persistent Memory (`remember`)
If you notice the agent repeatedly forgetting a rare pattern or a personal preference, tell it:
> "Remember that I prefer using `pytest` for unit tests."

The agent will store this in `.lord_code/memory.json` and recall it in every future session.

---

## 🛠 Commands

| Command | Description |
| :--- | :--- |
| `/help` | List all available slash commands |
| `/clear` | Clear the terminal and reset the banner |
| `/version` | Display current version information |
| `/exit`, `/quit` | Gracefully exit the session |

---

## 📁 File Structure & Working

### Core Logic
- **`src/agent/agent.py`**: The agent orchestrator. It now injects context before every request.
- **`src/agent/context.py`**: The `ContextManager` which locates and merges hierarchical context files.
- **`src/llm/client.py`**: Handles API communication and token usage tracking.

### Tool System
- **`src/tools/manager.py`**: Registers and coordinates tool execution.
- **`src/tools/file_ops.py`**: File system tools with recursive listing capabilities.
- **`src/tools/shell.py`**: Secure shell execution tool.
- **`src/tools/memory.py`**: Implements the `remember` and `recall` tools for long-term storage.

### Safety & Utilities
- **`src/safety/guardrail.py`**: Centralized security validation for paths and commands.
- **`src/tools/utils.py`**: Path resolution and project root detection.

### UI & UX
- **`src/cli/app.py`**: Manages the REPL loop and slash commands.
- **`src/cli/theme.py`**: Provides rich formatting for the AI and tool responses.

---

## 🎨 UI/UX Features

- **Terminal Previews**: Visual log of shell commands before execution.
- **Approval Workflow**: Interactive `(y/n)` prompts for high-risk actions.
- **Token Usage**: Subtle footer indicating resource consumption per-request.

---
