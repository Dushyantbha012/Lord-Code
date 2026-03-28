# Lord Code - AI Coding Agent

Lord Code is a CLI-based agentic coding assistant powered by the Groq API. It operates in a tight think-act-observe loop, enabling it to autonomously execute tools to explore codebases, run shell commands, and modify files.

## Features

- **Agentic Loop**: Autonomous reasoning and tool execution.
- **Smart Context Awareness**: Automatically gathers directory tree, git status, and key file summaries to provide the models with deep codebase awareness.
- **Multi-Model Support**: Switch between high-performance Groq models and compound systems at runtime.
- **Advanced Toolset**:
  - File operations: read, write, **diff-based edit** (search/replace blocks with unified diff preview).
  - Smart search: find files by pattern, search text within files, find code definitions.
  - Git integration: commit, branch, diff, stash/unstash, status — all with safety confirmation.
  - Shell execution with safety rails.
  - **Automatic linting**: Detects project linter and auto-runs after edits with `--fix` mode.
  - **Test execution**: Auto-detects test frameworks and runs tests with retry logic (max 3 attempts).
- **Undo/Rollback System**: Automatic checkpoints before every file modification, with `/undo` to revert.
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
- `/undo`: Revert the last set of AI-made file changes.
- `/changes`: Show a log of all file modifications in the current session.
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

Lord Code is equipped with a comprehensive set of tools:

### File Operations

| Tool | Description |
| --- | --- |
| `read_file` | Read the contents of a file. |
| `write_file` | Create or overwrite a file (use for new files). |
| `edit_file` | **Edit existing files using search/replace blocks** — shows a unified diff preview. Preferred over `write_file` for modifications. |

### Search Tools

| Tool | Description |
| --- | --- |
| `find_files` | Find files by name/glob pattern (respects `.gitignore`). |
| `search_in_files` | Search for text across project files (like ripgrep). |
| `find_definition` | Locate function, class, or variable definitions. |
| `grep_search` | Regex pattern search across files. |

### Git Tools

| Tool | Description |
| --- | --- |
| `get_git_diff` | See uncommitted staged/unstaged changes. |
| `get_git_log` | View recent git commits. |
| `git_commit` | Stage all changes and commit with a message. |
| `git_create_branch` | Create and checkout a new branch. |
| `git_diff_ref` | Diff against a branch, tag, or commit hash. |
| `git_stash` | Stash uncommitted changes. |
| `git_unstash` | Pop the most recent stash entry. |
| `git_status` | Show concise git status. |

### Development Tools

| Tool | Description |
| --- | --- |
| `execute_command` | Run shell commands in the terminal. |
| `run_tests` | Run the project's test suite (auto-detects pytest, npm, cargo, go). |

## Automatic Linting

After any file modification (`write_file` or `edit_file`), Lord Code automatically:
1. Detects the project's linter from config files (ruff, black, flake8, eslint, prettier, rustfmt, gofmt).
2. Runs the linter with `--fix` mode for auto-correctable issues.
3. If lint errors remain, feeds them back to the AI for self-correction.

## Test Execution

The `run_tests` tool auto-detects your test framework:
- **Python**: pytest (from `pytest.ini`, `conftest.py`, or `pyproject.toml`)
- **JavaScript**: npm test (from `package.json`)
- **Rust**: cargo test (from `Cargo.toml`)
- **Go**: go test (from `go.mod`)

If tests fail, the AI can retry up to 3 times per user turn before stopping and reporting.

## Undo/Rollback System

Lord Code creates automatic checkpoints before every file modification:
- **`/undo`**: Reverts the most recent set of changes (all edits from one AI turn).
- **`/changes`**: Shows a log of all modifications in the current session.
- Supports reverting multiple turns (LIFO order).
- Newly created files are deleted on undo; modified files are restored to their original content.

> **Note**: Undo history is session-scoped (in-memory only). It is not persisted across sessions.

## Project Structure

- `src/main.py`: Entry point and project context initialization.
- `src/cli/`: Terminal chat loop, safety checks, and session management.
- `src/context/`: Core logic for context gathering, token tracking, and configuration.
- `src/llm/`: LLM client factory and provider implementations.
- `src/tools/`: Tool definitions, handlers, and specialized modules:
  - `definitions.py`: Tool schema definitions for the LLM.
  - `handlers.py`: Tool execution registry with undo integration.
  - `edit_file.py`: Diff-based editing engine (search/replace + unified diff).
  - `git_tools.py`: Git integration (commit, branch, stash, etc.).
  - `linter.py`: Automatic linter detection and execution.
  - `test_runner.py`: Test framework detection and execution.
  - `undo.py`: Checkpoint and rollback system.
  - `search.py`: Smart search implementations.
- `src/config.py`: Centralized configuration and model metadata.
