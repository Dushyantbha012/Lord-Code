# 🤖 Lord-Code — AI Coding Agent

A terminal-based AI coding assistant powered by Groq's ultra-fast inference API. Lord-Code can read, write, and execute code in your projects through natural conversation.

## Features

- 🧠 **Intelligent Conversations** — Chat naturally about your code
- 📁 **File Operations** — Read, write, and explore project files
- ⚡ **Command Execution** — Run shell commands with safety guardrails
- 🔄 **Agentic Loop** — Multi-step tool chains that self-correct on errors
- 🛡️ **Tri-Mode Safety** — Paranoid, Smart, or YOLO modes for tool approval
- 📡 **Streaming Responses** — Real-time token streaming from Groq
- 💰 **Cost Tracking** — Token usage and cost estimation per session
- 🔀 **Multi-Provider** — Switch between Groq and Ollama (local) on the fly

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/your-repo/Lord-Code.git
cd Lord-Code
python3 -m venv .venv
source .venv/bin/activate
pip install groq openai rich prompt-toolkit click python-dotenv pathspec aiofiles
```

### 2. Set Up API Key

Get a free Groq API key at [console.groq.com](https://console.groq.com).

```bash
echo "GROQ_API_KEY=your-key-here" > .env
```

### 3. Run

```bash
python -m src.main
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
| `/provider <groq\|ollama>` | Switch LLM provider |
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
│   ├── groq_adapter.py  # Groq SDK adapter
│   ├── ollama_adapter.py # Ollama (OpenAI-compat)
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