# Lord Code - AI Coding Agent

Lord Code is a CLI-based agentic coding assistant powered by the Groq API. It operates in a tight think-act-observe loop, enabling it to autonomously execute tools to explore codebases, run shell commands, and modify files.

## Features

- **Agentic Loop**: Autonomous reasoning and tool execution.
- **Support for Multiple Models**: Switch between high-performance Groq models and compound systems at runtime.
- **Tool-Use Capabilities**:
  - Read and write files.
  - List directory structures.
  - Execute shell commands with safety rails.
  - Code search and grep functionality.
- **Safety Rails**: Restricted command execution, path boundaries, and confirmation prompts for destructive actions.
- **Token Usage Tracking**: Monitor real-time token consumption and session aggregates.
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
   source venv/bin/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -e .
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
- `/models`: List all available Groq models.
- `/model <model_id>`: Switch the active LLM.
- `/reasoning-on`: Enable reasoning mode.
- `/reasoning-off`: Disable reasoning mode.
- `/exit` or `/quit`: Gracefully exit the session.

## Configuration

Available models are configured in `src/config.py`. Current supported models include:
- `openai/gpt-oss-120b` (Default)
- `openai/gpt-oss-20b`
- `llama-3.3-70b-versatile`
- `llama-3.1-8b-instant`
- `groq/compound`
- `groq/compound-mini`

## Project Structure

- `src/main.py`: Entry point for the application.
- `src/cli/`: Logic for the terminal chat loop and safety checks.
- `src/llm/`: LLM provider implementations (modularized by model).
- `src/tools/`: Definitions and handlers for agentic tools.
- `src/config.py`: Centralized configuration.
