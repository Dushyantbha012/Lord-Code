import sys
import signal
import os
from typing import List, Dict, Optional
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from src.llm.base import BaseLLM
from src.config import Config
from src.context.token_manager import TokenManager
from src.context.project_config import ProjectConfig


class ChatLoop:
    def __init__(self, llm: BaseLLM, project_context: str = "", project_config: Optional[ProjectConfig] = None):
        self.llm = llm
        self.console = Console()
        self.working_dir = os.getcwd()
        self.project_config = project_config or ProjectConfig()

        # ── Build System Prompt with Project Context ──
        system_content = self._build_system_prompt(project_context)
        self.messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_content}
        ]
        self.reasoning_enabled = False

        # ── Token Manager (Feature 2.3) ──
        self.token_manager = TokenManager(
            model=getattr(llm, 'model', Config.DEFAULT_MODEL),
            token_budget=self.project_config.token_budget,
        )

        # Handle Ctrl+C
        signal.signal(signal.SIGINT, self._handle_exit)

    def _build_system_prompt(self, project_context: str) -> str:
        """Build a rich system prompt with project context and instructions."""
        parts = [
            "You are Lord Code, a powerful AI coding assistant that lives in the terminal.",
            f"Your working directory is: {self.working_dir}",
            "Always assume relative paths are relative to this directory unless specified otherwise.",
            "",
            "You have access to tools for reading/writing files, executing commands, and searching code.",
            "Use the most appropriate tool for each task. Prefer search_in_files and find_definition",
            "over manual grep when looking for code patterns or definitions.",
            "",
        ]

        if project_context:
            parts.append("## Project Context (auto-gathered)")
            parts.append(project_context)
            parts.append("")

        if self.project_config.custom_instructions:
            parts.append("## Custom Instructions")
            parts.append(self.project_config.custom_instructions)
            parts.append("")

        return "\n".join(parts)

    def _handle_exit(self, signum, frame):
        self.console.print("\n[bold red]Exiting gracefully...[/bold red]")
        sys.exit(0)

    def _display_welcome(self):
        self.console.print("[bold cyan]Welcome to Lord Code![/bold cyan]")
        self.console.print(f"Current Model: [bold green]{self.llm.model}[/bold green]")
        self.console.print(f"Working Directory: [bold blue]{self.working_dir}[/bold blue]")
        
        # Show context usage
        sys_tokens = self.token_manager.count_message_tokens(self.messages)
        budget = self.token_manager.get_budget()
        self.console.print(f"Context: [dim]{sys_tokens:,} / {budget['context_limit']:,} tokens used[/dim]")
        
        self.console.print("Type [bold yellow]/exit[/bold yellow] or [bold yellow]/quit[/bold yellow] to leave.")
        self.console.print(
            "Commands: [green]/models[/green], [green]/model <id>[/green], "
            "[green]/reasoning-on[/green], [green]/reasoning-off[/green], "
            "[green]/context[/green]"
        )
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
                if user_input in ("/exit", "/quit"):
                    self._handle_exit(None, None)

                # ── Slash Commands ──
                if user_input == "/models":
                    self.console.print("[bold cyan]Available Models:[/bold cyan]")
                    for m in Config.AVAILABLE_MODELS:
                        star = "*" if m == self.llm.model else " "
                        reasoning_opt = "[reasoning]" if m in Config.REASONING_MODELS else ""
                        ctx = Config.MODEL_CONTEXT_LIMITS.get(m, "?")
                        self.console.print(f" {star} {m} {reasoning_opt} ({ctx:,} ctx)")
                    continue
                
                if user_input.startswith("/model "):
                    new_model = user_input.split(" ", 1)[1].strip()
                    if new_model in Config.AVAILABLE_MODELS:
                        from src.llm.groq.factory import get_llm_client
                        self.llm = get_llm_client(new_model)
                        self.token_manager.update_model(new_model)
                        self.console.print(f"[bold green]Switched to model: {new_model}[/bold green]")
                        if new_model not in Config.REASONING_MODELS and self.reasoning_enabled:
                            self.reasoning_enabled = False
                            self.console.print("[bold yellow]Note: Reasoning mode disabled as it's not recommended for this model.[/bold yellow]")
                    else:
                        self.console.print(f"[bold red]Error: Model '{new_model}' not found in available models.[/bold red]")
                    continue

                if user_input == "/reasoning-on":
                    if self.llm.model in Config.REASONING_MODELS:
                        self.reasoning_enabled = True
                        self.console.print("[bold green]Reasoning mode enabled.[/bold green]")
                    else:
                        self.console.print(f"[bold yellow]Warning: Reasoning is not explicitly optimized for {self.llm.model}, but enabling anyway.[/bold yellow]")
                        self.reasoning_enabled = True
                    continue

                if user_input == "/reasoning-off":
                    self.reasoning_enabled = False
                    self.console.print("[bold yellow]Reasoning mode disabled.[/bold yellow]")
                    continue

                if user_input == "/context":
                    self._display_context_info()
                    continue

                # ── Process User Message ──
                self.messages.append({"role": "user", "content": user_input})

                # Check if summarization is needed before sending to LLM
                if self.token_manager.should_summarize(self.messages):
                    self.console.print("[dim yellow]⚡ Context getting large — summarizing older messages...[/dim yellow]")
                    self.messages = self.token_manager.summarize_messages(self.messages, self.llm)
                    self.console.print("[dim green]✓ Context summarized successfully.[/dim green]")

                last_turn_tokens = self._process_ai_response(TOOLS, TOOL_HANDLERS)
                
                # Display usage
                if last_turn_tokens:
                    conv_tokens = self.token_manager.get_conversation_tokens(self.messages)
                    budget = self.token_manager.get_budget()
                    self.console.print(
                        f"\n[dim magenta]Turn: {last_turn_tokens['total']} tokens "
                        f"(P: {last_turn_tokens.get('prompt', 0)}, C: {last_turn_tokens.get('completion', 0)}) "
                        f"| Context: {conv_tokens:,}/{budget['conversation']:,}[/dim magenta]"
                    )
                    self.total_tokens["prompt"] += last_turn_tokens.get("prompt", 0)
                    self.total_tokens["completion"] += last_turn_tokens.get("completion", 0)
                    self.total_tokens["total"] += last_turn_tokens.get("total", 0)

            except EOFError:
                self._handle_exit(None, None)
            except Exception as e:
                self.console.print(f"[bold red]Error:[/bold red] {str(e)}")

    def _display_context_info(self):
        """Display current token budget breakdown."""
        budget = self.token_manager.get_budget()
        sys_tokens = self.token_manager.count_message_tokens(
            [m for m in self.messages if m.get("role") == "system"]
        )
        conv_tokens = self.token_manager.get_conversation_tokens(self.messages)
        total_used = sys_tokens + conv_tokens

        self.console.print("\n[bold cyan]📊 Context Window Status[/bold cyan]")
        self.console.print(f"  Model:          {budget['model']}")
        self.console.print(f"  Context Limit:  {budget['context_limit']:,} tokens")
        self.console.print(f"  System Prompt:  {sys_tokens:,} / {budget['system_prompt']:,} tokens")
        self.console.print(f"  Conversation:   {conv_tokens:,} / {budget['conversation']:,} tokens")
        self.console.print(f"  Total Used:     {total_used:,} / {budget['context_limit']:,} tokens")
        self.console.print(f"  Summarize At:   {budget['summarize_at']:,} tokens")
        self.console.print(f"  Messages:       {len(self.messages)}")
        
        pct = (total_used / budget['context_limit']) * 100
        if pct > 80:
            self.console.print(f"  [bold red]⚠️  {pct:.1f}% used — summarization imminent[/bold red]")
        elif pct > 50:
            self.console.print(f"  [yellow]📈 {pct:.1f}% used[/yellow]")
        else:
            self.console.print(f"  [green]✓ {pct:.1f}% used[/green]")
        self.console.print()

    def _process_ai_response(self, tools, handlers) -> dict:
        import json
        from src.cli.safety import is_command_safe, is_path_safe, needs_confirmation
        
        self.console.print("\n[bold magenta]AI:[/bold magenta]", end=" ")
        
        full_response = ""
        tool_calls = []
        usage = None
        root_dir = self.working_dir
        
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
