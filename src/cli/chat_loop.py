import sys
import signal
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
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ["/exit", "/quit"]:
                    self._handle_exit(None, None)
                
                if user_input == "/reasoning-on":
                    self.reasoning_enabled = True
                    self.console.print("[bold green]Reasoning mode enabled.[/bold green]")
                    continue
                
                if user_input == "/reasoning-off":
                    self.reasoning_enabled = False
                    self.console.print("[bold yellow]Reasoning mode disabled.[/bold yellow]")
                    continue

                self.messages.append({"role": "user", "content": user_input})
                
                self.console.print("\n[bold magenta]AI:[/bold magenta]", end=" ")
                
                full_response = ""
                with Live(Markdown(""), console=self.console, refresh_per_second=10) as live:
                    # For gpt-oss-120b on Groq, we stream the response.
                    for chunk in self.llm.chat(self.messages, stream=True, reasoning=self.reasoning_enabled):
                        full_response += chunk
                        live.update(Markdown(full_response))
                
                self.messages.append({"role": "assistant", "content": full_response})
                self.console.print() # New line after response

            except EOFError:
                self._handle_exit(None, None)
            except Exception as e:
                self.console.print(f"[bold red]Error:[/bold red] {str(e)}")
