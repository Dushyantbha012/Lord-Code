# Lord Code ✴

Lord Code is a professional AI Coding Agent CLI designed with a minimalist, high-end aesthetic inspired by modern agentic tools like Claude Code.

## 🚀 Getting Started

### Prerequisites
- **Python 3.9+**
- (Optional but recommended) A virtual environment (`venv`)

### 1. Installation
Clone the repository and install the project in editable mode from the root directory:

```bash
# Activate your virtual environment first
# For macOS/Linux:
source venv/bin/activate

# Install the project and dependencies
pip install -e .
```

### 2. Run the Application
You can start Lord Code using the following command:

```bash
lord-code
```

*Alternatively, you can run it as a module:*
```bash
python3 -m src.main
```

---

## 🎨 UI/UX Features

- **Premium Splash Screen**: A bold, Coral-themed startup UI with a custom block-style logo.
- **Minimalist REPL**: A clean chat interface (` › `) that stays out of your way.
- **Status Feedback**: Real-time "Thinking..." and "Processing..." indicators for AI interactions.
- **Unix Philosophy**: Minimalist, fast, and terminal-native.

## 🛠 Commands

Type these commands directly into the prompt:

| Command | Description |
| :--- | :--- |
| `/help` | List all available slash commands |
| `/clear` | Clear the terminal and reset the banner |
| `/version` | Display current version information |
| `/exit`, `/quit` | Gracefully exit the session |

## 📁 Project Structure

```text
Lord-Code/
├── src/
│   ├── cli/         # UI, Prompt, and REPL logic
│   ├── main.py      # Main entry point
│   └── config.py    # Global constants & commands
├── pyproject.toml   # Project dependencies & script mapping
└── setup.py         # Compatibility fallback for older pip versions
```

---
