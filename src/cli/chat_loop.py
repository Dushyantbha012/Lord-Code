import sys
import signal
import os
from typing import List, Dict
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from src.llm.base import BaseLLM
from src.config import Config

class ChatLoop:
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.console = Console()
        self.messages: List[Dict[str, str]] = [
            {"role": "system", "content": "You are a helpful AI assistant."}
        ]
        self.reasoning_enabled = False
        
        # Handle Ctrl+C
        signal.signal(signal.SIGINT, self._handle_exit)

    def _handle_exit(self, signum, frame):
        self.console.print("\n[bold red]Exiting gracefully...[/bold red]")
        sys.exit(0)

    def _display_welcome(self):
        self.console.print("[bold cyan]Welcome to the CLI Chat Loop![/bold cyan]")
        self.console.print("Type [bold yellow]/exit[/bold yellow] or [bold yellow]/quit[/bold yellow] to leave.")
        self.console.print("Commands: [green]/reasoning-on[/green], [green]/reasoning-off[/green]")
        self.console.print("-" * 50)

    def run(self):
        self._display_welcome()
        from src.tools.definitions import TOOLS
        from src.tools.handlers import TOOL_HANDLERS
        
        self.total_tokens = {"prompt": 0, "completion": 0, "total": 0}

        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input: continue
                if user_input.lower() in ["/exit", "/quit"]: self._handle_exit(None, None)
                if user_input == "/reasoning-on": self.reasoning_enabled = True; self.console.print("[bold green]Reasoning mode enabled.[/bold green]"); continue
                if user_input == "/reasoning-off": self.reasoning_enabled = False; self.console.print("[bold yellow]Reasoning mode disabled.[/bold yellow]"); continue

                self.messages.append({"role": "user", "content": user_input})
                last_turn_tokens = self._process_ai_response(TOOLS, TOOL_HANDLERS)
                
                # Display usage
                if last_turn_tokens:
                    self.console.print(f"\n[dim magenta]Usage this turn: {last_turn_tokens['total']} tokens "
                                     f"(P: {last_turn_tokens.get('prompt', 0)}, C: {last_turn_tokens.get('completion', 0)})[/dim magenta]")
                    self.total_tokens["prompt"] += last_turn_tokens.get("prompt", 0)
                    self.total_tokens["completion"] += last_turn_tokens.get("completion", 0)
                    self.total_tokens["total"] += last_turn_tokens.get("total", 0)

            except EOFError:
                self._handle_exit(None, None)
            except Exception as e:
                self.console.print(f"[bold red]Error:[/bold red] {str(e)}")

    def _process_ai_response(self, tools, handlers) -> dict:
        import json
        from src.cli.safety import is_command_safe, is_path_safe, needs_confirmation
        
        self.console.print("\n[bold magenta]AI:[/bold magenta]", end=" ")
        
        full_response = ""
        tool_calls = []
        usage = None
        root_dir = os.getcwd()
        
        with Live(Markdown(""), console=self.console, refresh_per_second=10) as live:
            for chunk in self.llm.chat(self.messages, stream=True, reasoning=self.reasoning_enabled, tools=tools):
                # Handle usage (if include_usage=True, it's often in the last chunk)
                if hasattr(chunk, 'usage') and chunk.usage:
                    usage = {
                        "prompt": chunk.usage.prompt_tokens,
                        "completion": chunk.usage.completion_tokens,
                        "total": chunk.usage.total_tokens
                    }

                if not chunk.choices: continue
                delta = chunk.choices[0].delta
                
                # Handle streaming content
                if delta.content:
                    full_response += delta.content
                    live.update(Markdown(full_response))
                
                # Handle tool calls
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        if len(tool_calls) <= tc_delta.index:
                            tool_calls.append({
                                "id": tc_delta.id,
                                "type": "function",
                                "function": {"name": tc_delta.function.name, "arguments": ""}
                            })
                        if tc_delta.function.arguments:
                            tool_calls[tc_delta.index]["function"]["arguments"] += tc_delta.function.arguments

        if full_response:
            self.messages.append({"role": "assistant", "content": full_response})
            self.console.print()

        if tool_calls:
            self.messages.append({
                "role": "assistant",
                "tool_calls": tool_calls,
                "content": full_response or None
            })
            
            for tc in tool_calls:
                name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                
                # Safety Checks
                if name == "execute_command":
                    cmd = args.get("command", "")
                    if not is_command_safe(cmd):
                        self.console.print(f"[bold red]Blocked dangerous command:[/bold red] {cmd}")
                        self._add_tool_result(tc["id"], name, "Error: Command was blocked for safety.")
                        continue
                
                if "path" in args:
                    if not is_path_safe(args["path"], root_dir):
                        self.console.print(f"[bold red]Blocked out-of-bounds path:[/bold red] {args['path']}")
                        self._add_tool_result(tc["id"], name, "Error: Path access restricted to project directory.")
                        continue

                # Confirmation for destructive actions
                if needs_confirmation(name):
                    self.console.print(f"\n[bold yellow]Safety Check:[/bold yellow] AI wants to run {name}({args})")
                    confirm = input("Approve? (y/n): ").strip().lower()
                    if confirm != 'y':
                        self.console.print("[bold yellow]Tool execution cancelled by user.[/bold yellow]")
                        self._add_tool_result(tc["id"], name, "Error: User denied permission for this action.")
                        continue

                self.console.print(f"[bold blue]Executing Tool:[/bold blue] {name}({args})")
                handler = handlers.get(name)
                result = handler(**args) if handler else f"Error: Tool {name} not found."
                
                display_result = result[:500] + "..." if len(result) > 500 else result
                self.console.print(f"[bold green]Tool Result:[/bold green]\n{display_result}")
                self._add_tool_result(tc["id"], name, result)
            
            # Recurse and accumulate usage
            next_usage = self._process_ai_response(tools, handlers)
            if next_usage and usage:
                usage["prompt"] += next_usage["prompt"]
                usage["completion"] += next_usage["completion"]
                usage["total"] += next_usage["total"]
            elif next_usage:
                usage = next_usage
                
        return usage

    def _add_tool_result(self, tool_call_id, name, result):
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": result
        })
