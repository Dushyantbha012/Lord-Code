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
from src.tools.undo import UndoManager
from src.tools.linter import run_linter
from src.ui.rich_ui import ui  # Feature 4.2 Rich UI
import time


class ChatLoop:
    def __init__(self, llm: BaseLLM, project_context: str = "", project_config: Optional[ProjectConfig] = None):
        self.llm = llm
        self.working_dir = os.getcwd()
        self.project_config = project_config or ProjectConfig()

        # ── Undo/Rollback System (Feature 3.5) ──
        self.undo_manager = UndoManager(self.working_dir)

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

        # ── Test Retry Counter (Feature 3.3) ──
        self._test_retry_count = 0
        self._max_test_retries = 3

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
            "",
            "## Tool Usage Guidelines",
            "- **Editing files**: Always prefer `edit_file` over `write_file` when modifying existing files.",
            "  `edit_file` uses search/replace blocks which is more efficient and safer.",
            "  Only use `write_file` for creating brand new files.",
            "- **Search**: Prefer `search_in_files` and `find_definition` over manual grep",
            "  when looking for code patterns or definitions.",
            "- **Testing**: After making code changes, use `run_tests` to verify correctness",
            "  if the project has a test suite.",
            "- **Git**: Use git tools (`git_commit`, `git_create_branch`, `git_status`, etc.)",
            "  for version control operations instead of `execute_command`.",
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
        ui.print("\n[bold red]Exiting gracefully...[/bold red]")
        sys.exit(0)

    def _display_welcome(self):
        ui.print("[bold cyan]Welcome to Lord Code![/bold cyan]")
        ui.print(f"Current Model: [bold green]{self.llm.model}[/bold green]")
        ui.print(f"Working Directory: [bold blue]{self.working_dir}[/bold blue]")
        
        # Show context usage
        sys_tokens = self.token_manager.count_message_tokens(self.messages)
        budget = self.token_manager.get_budget()
        ui.print(f"Context: [dim]{sys_tokens:,} / {budget['context_limit']:,} tokens used[/dim]")
        
        ui.print("Type [bold yellow]/exit[/bold yellow] or [bold yellow]/quit[/bold yellow] to leave.")
        ui.print(
            "Commands: [green]/models[/green], [green]/model <id>[/green], "
            "[green]/reasoning-on[/green], [green]/reasoning-off[/green], "
            "[green]/context[/green], [green]/undo[/green], [green]/changes[/green]"
        )
        ui.print("-" * 50)

    def run(self):
        self._display_welcome()
        from src.tools.definitions import TOOLS
        from src.tools.handlers import TOOL_HANDLERS, set_undo_manager
        
        # Inject undo manager into handlers
        set_undo_manager(self.undo_manager)
        
        self.total_tokens = {"prompt": 0, "completion": 0, "total": 0}

        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input: continue
                if user_input in ("/exit", "/quit"):
                    self._handle_exit(None, None)

                # ── Slash Commands ──
                if user_input == "/models":
                    ui.print("[bold cyan]Available Models:[/bold cyan]")
                    for m in Config.AVAILABLE_MODELS:
                        star = "*" if m == self.llm.model else " "
                        reasoning_opt = "[reasoning]" if m in Config.REASONING_MODELS else ""
                        ctx = Config.MODEL_CONTEXT_LIMITS.get(m, "?")
                        ui.print(f" {star} {m} {reasoning_opt} ({ctx:,} ctx)")
                    continue
                
                if user_input.startswith("/model "):
                    new_model = user_input.split(" ", 1)[1].strip()
                    if new_model in Config.AVAILABLE_MODELS:
                        from src.llm.groq.factory import get_llm_client
                        self.llm = get_llm_client(new_model)
                        self.token_manager.update_model(new_model)
                        ui.print(f"[bold green]Switched to model: {new_model}[/bold green]")
                        if new_model not in Config.REASONING_MODELS and self.reasoning_enabled:
                            self.reasoning_enabled = False
                            ui.print("[bold yellow]Note: Reasoning mode disabled as it's not recommended for this model.[/bold yellow]")
                    else:
                        ui.print(f"[bold red]Error: Model '{new_model}' not found in available models.[/bold red]")
                    continue

                if user_input == "/reasoning-on":
                    if self.llm.model in Config.REASONING_MODELS:
                        self.reasoning_enabled = True
                        ui.print("[bold green]Reasoning mode enabled.[/bold green]")
                    else:
                        ui.print(f"[bold yellow]Warning: Reasoning is not explicitly optimized for {self.llm.model}, but enabling anyway.[/bold yellow]")
                        self.reasoning_enabled = True
                    continue

                if user_input == "/reasoning-off":
                    self.reasoning_enabled = False
                    ui.print("[bold yellow]Reasoning mode disabled.[/bold yellow]")
                    continue

                if user_input == "/context":
                    self._display_context_info()
                    continue

                # ── Undo Command (Feature 3.5) ──
                if user_input == "/undo":
                    result = self.undo_manager.undo_last()
                    ui.print(f"\n[bold cyan]Undo:[/bold cyan]\n{result}\n")
                    continue

                # ── Change Log Command (Feature 3.5) ──
                if user_input == "/changes":
                    log = self.undo_manager.get_change_log()
                    ui.print(f"\n[bold cyan]{log}[/bold cyan]\n")
                    continue

                # ── Process User Message ──
                self.messages.append({"role": "user", "content": user_input})

                # Reset test retry counter for new user message
                self._test_retry_count = 0

                # Check if summarization is needed before sending to LLM
                if self.token_manager.should_summarize(self.messages):
                    ui.print("[dim yellow]⚡ Context getting large — summarizing older messages...[/dim yellow]")
                    self.messages = self.token_manager.summarize_messages(self.messages, self.llm)
                    ui.print("[dim green]✓ Context summarized successfully.[/dim green]")

                # Begin an undo turn for this AI response
                self.undo_manager.begin_turn("AI edit")

                last_turn_tokens = self._process_ai_response(TOOLS, TOOL_HANDLERS)

                # End the undo turn
                self.undo_manager.end_turn()
                
                # Display usage
                if last_turn_tokens:
                    conv_tokens = self.token_manager.get_conversation_tokens(self.messages)
                    budget = self.token_manager.get_budget()
                    ui.print(
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
                ui.print(f"[bold red]Error:[/bold red] {str(e)}")

    def _display_context_info(self):
        """Display current token budget breakdown."""
        budget = self.token_manager.get_budget()
        sys_tokens = self.token_manager.count_message_tokens(
            [m for m in self.messages if m.get("role") == "system"]
        )
        conv_tokens = self.token_manager.get_conversation_tokens(self.messages)
        total_used = sys_tokens + conv_tokens

        ui.print("\n[bold cyan]📊 Context Window Status[/bold cyan]")
        ui.print(f"  Model:          {budget['model']}")
        ui.print(f"  Context Limit:  {budget['context_limit']:,} tokens")
        ui.print(f"  System Prompt:  {sys_tokens:,} / {budget['system_prompt']:,} tokens")
        ui.print(f"  Conversation:   {conv_tokens:,} / {budget['conversation']:,} tokens")
        ui.print(f"  Total Used:     {total_used:,} / {budget['context_limit']:,} tokens")
        ui.print(f"  Summarize At:   {budget['summarize_at']:,} tokens")
        ui.print(f"  Messages:       {len(self.messages)}")
        
        pct = (total_used / budget['context_limit']) * 100
        if pct > 80:
            ui.print(f"  [bold red]⚠️  {pct:.1f}% used — summarization imminent[/bold red]")
        elif pct > 50:
            ui.print(f"  [yellow]📈 {pct:.1f}% used[/yellow]")
        else:
            ui.print(f"  [green]✓ {pct:.1f}% used[/green]")
        ui.print()

    def _run_lint_after_edit(self, file_path: str) -> None:
        """
        Automatic Linting (Feature 3.2).
        Runs after write_file or edit_file to catch issues early.
        """
        lint_result = run_linter(file_path, self.working_dir)
        if lint_result is None:
            return  # No linter available for this file type

        if lint_result.success:
            fix_note = " (auto-fixed)" if lint_result.auto_fixed else ""
            ui.print(f"  [green]✓ Lint passed ({lint_result.linter_name}){fix_note}[/green]")
        else:
            ui.print(f"  [yellow]⚠ Lint errors ({lint_result.linter_name}):[/yellow]")
            # Truncate for display
            display_output = lint_result.output[:500]
            ui.print(f"  [dim]{display_output}[/dim]")
            
            # Feed errors back to the LLM as a system message
            self.messages.append({
                "role": "user",
                "content": (
                    f"[SYSTEM — Auto-Lint] {lint_result.linter_name} reported errors in {file_path}:\n"
                    f"{lint_result.output}\n\n"
                    f"Please fix these lint issues."
                ),
            })
            ui.print(f"  [yellow]→ Feeding lint errors back to AI for correction...[/yellow]")

    def _process_ai_response(self, tools, handlers) -> dict:
        import json
        from src.cli.safety import is_command_safe, is_path_safe, needs_confirmation
        
        ui.print("\n[bold magenta]AI:[/bold magenta]", end=" ")
        
        full_response = ""
        tool_calls = []
        usage = None
        root_dir = self.working_dir
        
        ui.start_spinner(f"AI is thinking...")
        
        with ui.live_markdown() as live:
            it = self.llm.chat(self.messages, stream=True, reasoning=self.reasoning_enabled, tools=tools)
            
            # Start streaming
            for chunk in it:
                # Stop spinner on first chunk
                ui.stop_spinner()
                
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
                    live.refresh()
                
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

        # Graceful spinner cleanup if no chunks were yielded
        ui.stop_spinner()

        if full_response:
            self.messages.append({"role": "assistant", "content": full_response})
            ui.print()

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
                        ui.print(f"[bold red]Blocked dangerous command:[/bold red] {cmd}")
                        self._add_tool_result(tc["id"], name, "Error: Command was blocked for safety.")
                        continue
                
                if "path" in args:
                    if not is_path_safe(args["path"], root_dir):
                        ui.print(f"[bold red]Blocked out-of-bounds path:[/bold red] {args['path']}")
                        self._add_tool_result(tc["id"], name, "Error: Path access restricted to project directory.")
                        continue

                # Confirmation for destructive actions
                if needs_confirmation(name):
                    ui.print(f"\n[bold yellow]Safety Check:[/bold yellow] AI wants to run {name}({args})")
                    confirm = input("Approve? (y/n): ").strip().lower()
                    if confirm != 'y':
                        ui.print("[bold yellow]Tool execution cancelled by user.[/bold yellow]")
                        self._add_tool_result(tc["id"], name, "Error: User denied permission for this action.")
                        continue

                ui.print_tool_call(name, args)
                ui.start_spinner(f"Executing {name}...")
                
                handler = handlers.get(name)
                result = handler(**args) if handler else f"Error: Tool {name} not found."
                
                ui.stop_spinner()
                ui.print_tool_result(result, name)
                self._add_tool_result(tc["id"], name, result)

                # ── Auto-Lint after file edits (Feature 3.2) ──
                if name in ("write_file", "edit_file") and not result.startswith("Error"):
                    file_path = args.get("path", "")
                    if file_path:
                        self._run_lint_after_edit(file_path)

                # ── Test retry logic (Feature 3.3) ──
                if name == "run_tests" and "FAILED" in result:
                    self._test_retry_count += 1
                    if self._test_retry_count < self._max_test_retries:
                        ui.print(
                            f"  [yellow]⚠ Tests failed (attempt {self._test_retry_count}/{self._max_test_retries})"
                            f" — AI will attempt to fix...[/yellow]"
                        )
                    else:
                        ui.print(
                            f"  [bold red]✖ Max test retries ({self._max_test_retries}) reached. "
                            f"Manual intervention needed.[/bold red]"
                        )
                        # Add a message to stop the LLM from retrying
                        self.messages.append({
                            "role": "user",
                            "content": (
                                "[SYSTEM] Maximum test retry limit reached. "
                                "Stop attempting to fix and summarize the remaining failures for the user."
                            ),
                        })

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
