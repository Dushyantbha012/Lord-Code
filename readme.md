# 🤖 Lord-Code — AI Coding Agent

A terminal-based AI coding assistant powered by Groq's ultra-fast inference API. Lord-Code can read, write, and execute code in your projects through natural conversation.

## Features

- 🧠 **Intelligent Conversations** — Chat naturally about your code
- 📁 **File Operations** — Read, write, and explore project files
- ⚡ **Command Execution** — Run shell commands with safety guardrails
- 🔄 **Agentic Loop** — Multi-step tool chains that self-correct on errors
- 🛡️ **Tri-Mode Safety** — Paranoid, Smart, or YOLO modes for tool approval
- 📡 **Streaming Responses** — Real-time token streaming across supported providers
- 💰 **Cost Tracking** — Token usage and cost estimation per session (with provider-specific pricing)
- 🔀 **Multi-Provider** — Switch between Groq, OpenAI, Anthropic, Gemini, and Ollama (local) on the fly

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/your-repo/Lord-Code.git
cd Lord-Code
python3 -m venv .venv
source .venv/bin/activate
# Using Poetry (recommended):
poetry install
# Using pip (easiest for global CLI):
pip install -e .
```

### 2. Global CLI Setup (Recommended)

To run **lordcode** from any folder on your machine, add a shortcut to your terminal profile:

```bash
# Get the absolute path to your venv binary
echo "alias lordcode='$(pwd)/.venv/bin/lordcode'" >> ~/.zshrc
source ~/.zshrc
```

Now you can `cd` into any project and just type `lordcode`.

### 3. Set Up API Keys

Get API keys for the providers you want to use:
- **Groq** (Default, very fast): [console.groq.com](https://console.groq.com)
- **OpenAI**: [platform.openai.com](https://platform.openai.com)
- **Anthropic**: [console.anthropic.com](https://console.anthropic.com)
- **Gemini**: [aistudio.google.com](https://aistudio.google.com)

```bash
# Add keys to your .env file
echo "GROQ_API_KEY=your-key" >> .env
echo "OPENAI_API_KEY=your-key" >> .env
echo "ANTHROPIC_API_KEY=your-key" >> .env
echo "GEMINI_API_KEY=your-key" >> .env
```

### 4. Run

Inside the project directory:
```bash
python3 -m src.main
```

Across any project directory (using the alias):
```bash
cd /path/to/any/project
lordcode
```

## Usage

### Basic Conversation
```
[smart] You ❯ What files are in this project?
🔧 Calling list_directory...
📁 Listed project root/

The project contains the following structure...

[smart] You ❯ Read the main.py and add error handling
🔧 Calling read_file...
📄 Read src/main.py (150 lines, 4.2KB)
🔧 Calling write_file...
✏️  Modified src/main.py (+12 lines, now 162 lines)
```

### Slash Commands

| Command | Description |
|---|---|
| `/help` | Show all commands |
| `/exit` | End session |
| `/clear` | Clear conversation history |
| `/mode <paranoid\|smart\|yolo>` | Change safety mode |
| `/provider <name>` | Switch LLM provider (groq/openai/anthropic/gemini/ollama) |
| `/providers` | List all available providers and your API key status |
| `/model <name>` | Switch model |
| `/cost` | Show token usage and cost |
| `/history` | Show conversation history |
| `/retry` | Re-send last message |
| `/info` | Show current configuration |

### Safety Modes

| Mode | Behavior |
|---|---|
| **paranoid** | Confirm every tool call (including reads) |
| **smart** (default) | Auto-approve reads, confirm writes & commands |
| **yolo** | Auto-approve everything (blocklist still active) |

### CLI Options

```bash
python -m src.main --help
python -m src.main --provider openai --model gpt-4o
python -m src.main --provider ollama --model llama3.1:8b
python -m src.main --mode yolo --no-stream

python -m src.main -v  # verbose mode
```

## Architecture

```
src/
├── main.py              # CLI entry point (Click)
├── config.py            # Configuration system
├── cli/
│   ├── interface.py     # Async prompt loop
│   ├── formatter.py     # Rich terminal rendering
│   └── commands.py      # Slash command handler
├── llm/
│   ├── base.py          # Abstract adapter + types
│   ├── groq_adapter.py  # Groq SDK adapter (default)
│   ├── openai_adapter.py # OpenAI ChatGPT adapter
│   ├── anthropic_adapter.py # Anthropic Claude adapter
│   ├── gemini_adapter.py # Google Gemini adapter
│   ├── ollama_adapter.py # Ollama (local models)
│   └── provider.py      # Provider manager
├── agent/
│   ├── loop.py          # Core agentic loop
│   ├── history.py       # Conversation & token tracking
│   └── system_prompt.py # Dynamic prompt builder
├── tools/
│   ├── base.py          # Tool base class
│   ├── registry.py      # Tool registry
│   ├── read_file.py     # 📄 Read files
│   ├── write_file.py    # ✏️  Write files
│   ├── list_directory.py # 📁 List directories
│   └── run_command.py   # ⚡ Run shell commands
└── safety/
    ├── blocklist.py     # Command & path security
    └── confirmation.py  # Tri-mode confirmation
```

## Running Tests

```bash
python -m pytest tests/ -v
```

## License

MIT