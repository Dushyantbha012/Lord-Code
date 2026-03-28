# Lord Code - AI Coding Agent

Lord Code is a CLI-based agentic coding assistant powered by the Groq API. It operates in a tight think-act-observe loop, enabling it to autonomously execute tools to explore codebases, run shell commands, and modify files.

## Features

- **Agentic Loop**: Autonomous reasoning and tool execution.
- **Smart Context Awareness**: Automatically gathers directory tree, git status, and key file summaries to provide the models with deep codebase awareness.
- **Multi-Model Support**: Switch between high-performance Groq models and compound systems at runtime.
- **Advanced Toolset**:
  - File operations: read, write, list.
  - Smart search: find files by pattern, search text within files, find code definitions.
  - Git integration: view diffs and logs directly from the terminal.
  - Shell execution with safety rails.
- **Intelligent Context Management**: Real-time token tracking and automated conversation summarization to maximize context efficiency.
- **Project Configuration**: Custom behavior via `.lordcode.yaml`.
- **Safety Rails**: Blocked dangerous commands, path boundary checks, and confirmation prompts for destructive actions.
- **Streaming Output**: Responsive real-time Markdown-rendered responses.

## Getting Started

### Prerequisites

- Python 3.10+
- A [Groq Cloud](https://console.groq.com/) API Key.

### Installation

1. Clone the repository.
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -e .
   pip install tiktoken pathspec pyyaml
   ```
4. Configure your `.env` file:
   ```bash
   echo "GROQ_API_KEY=your_groq_api_key_here" > .env
   ```

### Usage

Run the agent:
```bash
python3 src/main.py
```

### CLI Commands

While in the chat loop, use slash commands to control the agent:
- `/models`: List all available Groq models and their context limits.
- `/model <model_id>`: Switch the active LLM.
- `/reasoning-on`: Enable reasoning mode.
- `/reasoning-off`: Disable reasoning mode.
- `/context`: Show detailed token usage and budget breakdown.
- `/exit` or `/quit`: Gracefully exit the session.

## Configuration (.lordcode.yaml)

You can customize Lord Code's behavior for specific projects by creating a `.lordcode.yaml` file in your project root:

```yaml
# .lordcode.yaml
model: openai/gpt-oss-120b
custom_instructions: |
  Always include type hints in Python.
  Follow PEP 8 styling.
ignored_paths:
  - data/
  - tmp/
preferred_tools:
  - find_definition
  - search_in_files
token_budget:
  system_prompt: 3000
  file_contents: 6000
```

## Tool Definitions

Lord Code is equipped with a variety of tools:

| Tool | Description |
| --- | --- |
| `read_file` | Read the contents of a file. |
| `write_file` | Create or overwrite a file. |
| `find_files` | Find files by name/glob pattern (respects `.gitignore`). |
| `search_in_files` | Search for text across project files (like ripgrep). |
| `find_definition` | Locate function, class, or variable definitions. |
| `get_git_diff` | See uncommitted staged/unstaged changes. |
| `get_git_log` | View recent git commits. |
| `execute_command` | Run shell commands in the terminal. |

## Project Structure

- `src/main.py`: Entry point and project context initialization.
- `src/cli/`: Terminal chat loop, safety checks, and session management.
- `src/context/`: Core logic for context gathering, token tracking, and configuration.
- `src/llm/`: LLM client factory and provider implementations.
- `src/tools/`: Tool definitions, search implementations, and command handlers.
- `src/config.py`: Centralized configuration and model metadata.
