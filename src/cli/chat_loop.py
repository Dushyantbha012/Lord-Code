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
from src.context.storage import StorageManager
from src.context.history import HistoryManager
from src.context.config_snapshots import ConfigSnapshotManager
from src.tools.undo import UndoManager
from src.tools.linter import run_linter
from src.agent.planner import PlanManager, PlanStatus, StepStatus
from src.ui.rich_ui import ui
import time


class ChatLoop:
    def __init__(self, llm: BaseLLM, project_context: str = "",
                 project_config: Optional[ProjectConfig] = None,
                 storage: Optional[StorageManager] = None):
        self.llm = llm
        self.working_dir = os.getcwd()
        self.project_config = project_config or ProjectConfig()

        # ── .lord-code Storage (Feature 5) ──
        self.storage = storage or StorageManager(self.working_dir)

        # ── Undo/Rollback System (Feature 3.5) ──
        self.undo_manager = UndoManager(self.working_dir)

        # ── Multi-Step Planner (Feature 4) — now uses .lord-code/plans/ ──
        self.plan_manager = PlanManager(self.working_dir, storage=self.storage)

        # ── History Manager (Feature 5) ──
        self.history_manager = HistoryManager(self.storage)

        # ── Config Snapshot Manager (Feature 5) ──
        self.config_snapshots = ConfigSnapshotManager(self.storage)

        # ── Build System Prompt with Project Context + History ──
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
            "## Planning",
            "- For complex, multi-step tasks, call `create_plan` FIRST before executing any other tools.",
            "- A task is \"complex\" if it involves 3+ file changes, architectural decisions, or multi-stage operations.",
            "- Simple tasks (reading a file, answering a question, a single edit) do NOT need a plan.",
            "- When executing a plan, work through steps one at a time and report progress.",
            "- If you discover that the plan needs adjustment mid-execution, call `update_plan` to modify it.",
            "- After each step is completed, briefly state the result before moving on.",
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

        # Auto-inject recent session history for better context
        recent_context = self.history_manager.get_recent_context(n_sessions=2)
        if recent_context:
            parts.append(recent_context)
            parts.append("")

        return "\n".join(parts)

    def _handle_exit(self, signum, frame):
        """Graceful exit — finalize history and exit."""
        self._finalize_session()
        ui.print("\n[bold red]Exiting gracefully...[/bold red]")
        sys.exit(0)

    def _finalize_session(self):
        """End the current history session with a summary."""
        try:
            summary = self.history_manager.generate_session_summary(self.messages)
            total_tokens = getattr(self, 'total_tokens', {}).get('total', 0)
            self.history_manager.end_session(
                summary=summary,
                token_count=total_tokens,
            )
        except Exception:
            pass  # Non-critical

    def _display_welcome(self):
        ui.print("[bold cyan]Welcome to Lord Code![/bold cyan]")
        ui.print(f"Current Model: [bold green]{self.llm.model}[/bold green]")
        ui.print(f"Working Directory: [bold blue]{self.working_dir}[/bold blue]")
        
        # Show context usage
        sys_tokens = self.token_manager.count_message_tokens(self.messages)
        budget = self.token_manager.get_budget()
        ui.print(f"Context: [dim]{sys_tokens:,} / {budget['context_limit']:,} tokens used[/dim]")

        # Show .lord-code stats
        stats = self.storage.get_stats()
        stat_parts = []
        if stats["session_count"] > 0:
            stat_parts.append(f"{stats['session_count']} past sessions")
        if stats["config_snapshot_count"] > 0:
            stat_parts.append(f"{stats['config_snapshot_count']} saved configs")
        if stats["has_active_plan"]:
            stat_parts.append("active plan")
        if stat_parts:
            ui.print(f"Storage: [dim]{', '.join(stat_parts)}[/dim]")

        # Show resumed plan if one exists
        if self.plan_manager.current_plan and self.plan_manager.current_plan.is_active:
            ui.print(f"\n[bold yellow]📋 Resumed plan:[/bold yellow] {self.plan_manager.current_plan.title}")
            ui.print_plan(self.plan_manager.current_plan)
        
        ui.print("Type [bold yellow]/exit[/bold yellow] or [bold yellow]/quit[/bold yellow] to leave.")
        ui.print(
            "Commands: [green]/models[/green], [green]/model <id>[/green], "
            "[green]/reasoning-on[/green], [green]/reasoning-off[/green], "
            "[green]/context[/green], [green]/undo[/green], [green]/changes[/green], "
            "[green]/plan[/green], [green]/history[/green], [green]/config[/green]"
        )
        ui.print("-" * 50)

    def run(self):
        self._display_welcome()
        from src.tools.definitions import TOOLS
        from src.tools.handlers import TOOL_HANDLERS, set_undo_manager, set_plan_manager
        
        # Inject undo manager into handlers
        set_undo_manager(self.undo_manager)
        # Inject plan manager into handlers
        set_plan_manager(self.plan_manager)

        # Start a new history session
        session_id = self.history_manager.start_session()
        
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

                # ── Plan Commands (Feature 4) ──
                if user_input.startswith("/plan"):
                    self._handle_plan_command(user_input)
                    continue

                # ── History Commands (Feature 5) ──
                if user_input.startswith("/history"):
                    self._handle_history_command(user_input)
                    continue

                # ── Config Snapshot Commands (Feature 5) ──
                if user_input.startswith("/config"):
                    self._handle_config_command(user_input)
                    continue

                # ── Process User Message ──
                self.messages.append({"role": "user", "content": user_input})
                self.history_manager.append_message({"role": "user", "content": user_input})

                # Reset test retry counter for new user message
                self._test_retry_count = 0

                # Check if summarization is needed before sending to LLM
                if self.token_manager.should_summarize(self.messages):
                    ui.print("[dim yellow]⚡ Context getting large — summarizing older messages...[/dim yellow]")
                    self.messages = self.token_manager.summarize_messages(self.messages, self.llm)
                    ui.print("[dim green]✓ Context summarized successfully.[/dim green]")

                # Begin an undo turn for this AI response
                self.undo_manager.begin_turn("AI edit")

                # Inject plan context if there's an active plan
                self._inject_plan_context()

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

    # ── History Commands ──────────────────────────────────────────────────

    def _handle_history_command(self, command: str):
        """Handle /history slash commands."""
        parts = command.strip().split(maxsplit=1)

        if len(parts) == 1:
            # /history — list recent sessions
            sessions = self.history_manager.list_sessions(n=10)
            if not sessions:
                ui.print("[dim]No past sessions found.[/dim]")
                return

            ui.print("\n[bold cyan]📜 Session History[/bold cyan]")
            for sess in sessions:
                ended = sess.get("ended_at", "unknown")[:16]
                msgs = sess.get("message_count", 0)
                tokens = sess.get("token_count", 0)
                summary = sess.get("summary", "No summary")[:80]
                sid = sess.get("id", "?")
                ui.print(
                    f"  [dim]{ended}[/dim] | [bold]{sid}[/bold] | "
                    f"{msgs} msgs, {tokens:,} tokens"
                )
                ui.print(f"    [dim]{summary}[/dim]")
            ui.print(f"\n[dim]Use /history <session_id> to view a session[/dim]\n")
            return

        # /history <session_id> — view a specific session
        session_id = parts[1].strip()
        messages = self.history_manager.load_session(session_id)
        if not messages:
            ui.print(f"[bold red]Session '{session_id}' not found.[/bold red]")
            return

        ui.print(f"\n[bold cyan]📜 Session: {session_id}[/bold cyan]")
        for msg in messages:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            ts = msg.get("_ts", "")[:16] if msg.get("_ts") else ""

            if role == "user" and content and not content.startswith("[SYSTEM"):
                ui.print(f"  [dim]{ts}[/dim] [bold cyan]You:[/bold cyan] {content[:200]}")
            elif role == "assistant":
                if content:
                    ui.print(f"  [dim]{ts}[/dim] [bold magenta]AI:[/bold magenta] {content[:200]}")
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        if isinstance(tc, dict) and "function" in tc:
                            ui.print(f"    [dim]→ Tool: {tc['function'].get('name', '?')}[/dim]")
            elif role == "tool":
                name = msg.get("name", "?")
                result_preview = (content[:80] + "...") if len(content) > 80 else content
                ui.print(f"    [dim]← {name}: {result_preview}[/dim]")
        ui.print()

    # ── Config Snapshot Commands ──────────────────────────────────────────

    def _handle_config_command(self, command: str):
        """Handle /config slash commands."""
        parts = command.strip().split(maxsplit=2)

        if len(parts) == 1:
            # /config — show help
            ui.print(
                "\n[bold cyan]⚙️ Configuration Commands[/bold cyan]\n"
                "  [green]/config save <name>[/green]   — Save current config as a snapshot\n"
                "  [green]/config list[/green]           — List saved config snapshots\n"
                "  [green]/config load <name>[/green]   — Restore a saved config\n"
                "  [green]/config delete <name>[/green] — Delete a snapshot\n"
                "  [green]/config export <name>[/green] — Export to .lordcode.yaml\n"
                "  [green]/config show[/green]           — Show current config\n"
            )
            return

        sub = parts[1].lower()

        if sub == "save":
            if len(parts) < 3:
                ui.print("[bold red]Usage: /config save <name>[/bold red]")
                return
            name = parts[2].strip()
            result = self.config_snapshots.save(
                name,
                self.project_config,
                model_id=self.llm.model,
                reasoning_enabled=self.reasoning_enabled,
            )
            ui.print(f"\n{result}\n")

        elif sub == "list":
            snapshots = self.config_snapshots.list_snapshots()
            if not snapshots:
                ui.print("[dim]No saved config snapshots.[/dim]")
                return
            ui.print("\n[bold cyan]⚙️ Saved Configurations[/bold cyan]")
            for snap in snapshots:
                saved = snap.get("saved_at", "?")[:16]
                model = snap.get("model", "?")
                ui.print(f"  [bold]{snap['name']}[/bold] — {model} [dim]({saved})[/dim]")
            ui.print()

        elif sub == "load":
            if len(parts) < 3:
                ui.print("[bold red]Usage: /config load <name>[/bold red]")
                return
            name = parts[2].strip()
            data = self.config_snapshots.load(name)
            if not data:
                ui.print(f"[bold red]Snapshot '{name}' not found.[/bold red]")
                return

            # Apply the config
            config_data = data.get("config", {})
            self.project_config = ProjectConfig.from_dict(config_data)

            # Switch model if specified
            saved_model = data.get("model")
            if saved_model and saved_model in Config.AVAILABLE_MODELS:
                from src.llm.groq.factory import get_llm_client
                self.llm = get_llm_client(saved_model)
                self.token_manager.update_model(saved_model)

            # Restore reasoning mode
            self.reasoning_enabled = data.get("reasoning_enabled", False)

            ui.print(f"\n[bold green]✅ Loaded config '{name}'[/bold green]")
            ui.print(f"  Model: {saved_model or 'unchanged'}")
            ui.print(f"  Reasoning: {'on' if self.reasoning_enabled else 'off'}")
            if self.project_config.custom_instructions:
                ui.print(f"  Custom instructions: yes")
            ui.print()

        elif sub == "delete":
            if len(parts) < 3:
                ui.print("[bold red]Usage: /config delete <name>[/bold red]")
                return
            name = parts[2].strip()
            result = self.config_snapshots.delete(name)
            ui.print(f"\n{result}\n")

        elif sub == "export":
            if len(parts) < 3:
                ui.print("[bold red]Usage: /config export <name>[/bold red]")
                return
            name = parts[2].strip()
            result = self.config_snapshots.export_snapshot(name)
            ui.print(f"\n{result}\n")

        elif sub == "show":
            ui.print("\n[bold cyan]⚙️ Current Configuration[/bold cyan]")
            ui.print(f"  Model:        {self.llm.model}")
            ui.print(f"  Reasoning:    {'on' if self.reasoning_enabled else 'off'}")
            ui.print(f"  Token Budget: {self.project_config.token_budget}")
            if self.project_config.custom_instructions:
                ui.print(f"  Custom Instr: {self.project_config.custom_instructions[:80]}...")
            if self.project_config.preferred_tools:
                ui.print(f"  Pref. Tools:  {', '.join(self.project_config.preferred_tools)}")
            custom_ignored = [p for p in self.project_config.ignored_paths
                              if p not in ProjectConfig.DEFAULT_IGNORED_PATHS]
            if custom_ignored:
                ui.print(f"  Extra Ignores: {', '.join(custom_ignored)}")
            ui.print()

        else:
            ui.print("[bold red]Unknown config command. Use /config for help.[/bold red]")

    # ── Plan Commands ─────────────────────────────────────────────────────

    def _handle_plan_command(self, command: str):
        """Handle /plan slash commands."""
        parts = command.strip().split(maxsplit=2)

        # /plan — show current plan
        if len(parts) == 1:
            if self.plan_manager.current_plan:
                ui.print_plan(self.plan_manager.current_plan)
            else:
                ui.print("[dim]No active plan.[/dim]")
            return

        sub = parts[1].lower()

        if sub == "approve":
            result = self.plan_manager.approve()
            ui.print(f"\n[bold cyan]{result}[/bold cyan]\n")
            if self.plan_manager.current_plan and self.plan_manager.current_plan.is_active:
                ui.print_plan(self.plan_manager.current_plan)

        elif sub == "reject":
            result = self.plan_manager.reject()
            ui.print(f"\n[bold cyan]{result}[/bold cyan]\n")

        elif sub == "skip":
            if len(parts) < 3:
                ui.print("[bold red]Usage: /plan skip <step_index>[/bold red]")
                return
            try:
                idx = int(parts[2])
                result = self.plan_manager.skip_step(idx)
                ui.print(f"\n{result}\n")
                if self.plan_manager.current_plan:
                    ui.print_plan(self.plan_manager.current_plan)
            except ValueError:
                ui.print("[bold red]Error: Step index must be a number.[/bold red]")

        elif sub == "clear":
            self.plan_manager.clear()
            ui.print("[bold yellow]Plan cleared.[/bold yellow]")

        elif sub == "modify":
            self._interactive_plan_edit()

        else:
            ui.print(
                "[bold yellow]Plan commands:[/bold yellow]\n"
                "  /plan            — Show current plan\n"
                "  /plan approve    — Approve pending plan\n"
                "  /plan reject     — Reject pending plan\n"
                "  /plan skip <n>   — Skip step n\n"
                "  /plan modify     — Edit the plan interactively\n"
                "  /plan clear      — Clear current plan"
            )

    def _interactive_plan_edit(self):
        """Interactive plan modification mode."""
        if not self.plan_manager.current_plan:
            ui.print("[dim]No active plan to edit.[/dim]")
            return

        ui.print_plan(self.plan_manager.current_plan)
        ui.print("\n[bold cyan]Plan Edit Mode[/bold cyan]")
        ui.print("  [green]add <description>[/green]     — Add a step at the end")
        ui.print("  [green]add <n> <description>[/green] — Insert a step at position n")
        ui.print("  [green]remove <n>[/green]             — Remove step n")
        ui.print("  [green]edit <n> <description>[/green] — Change step n's description")
        ui.print("  [green]done[/green]                   — Exit edit mode")
        ui.print()

        while True:
            try:
                edit_input = input("plan> ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not edit_input or edit_input.lower() == "done":
                break

            tokens = edit_input.split(maxsplit=2)
            action = tokens[0].lower()

            if action == "add":
                if len(tokens) >= 3 and tokens[1].isdigit():
                    idx = int(tokens[1])
                    desc = tokens[2]
                    result = self.plan_manager.add_step(desc, at_index=idx)
                elif len(tokens) >= 2:
                    desc = " ".join(tokens[1:])
                    result = self.plan_manager.add_step(desc)
                else:
                    ui.print("[red]Usage: add <description> or add <index> <description>[/red]")
                    continue
                ui.print(result)

            elif action == "remove":
                if len(tokens) < 2 or not tokens[1].isdigit():
                    ui.print("[red]Usage: remove <step_index>[/red]")
                    continue
                result = self.plan_manager.remove_step(int(tokens[1]))
                ui.print(result)

            elif action == "edit":
                if len(tokens) < 3 or not tokens[1].isdigit():
                    ui.print("[red]Usage: edit <step_index> <new description>[/red]")
                    continue
                result = self.plan_manager.modify_step(int(tokens[1]), tokens[2])
                ui.print(result)

            else:
                ui.print("[red]Unknown command. Use add, remove, edit, or done.[/red]")

        # Show final state
        ui.print()
        ui.print_plan(self.plan_manager.current_plan)

    # ── Plan Context Injection ────────────────────────────────────────────

    def _inject_plan_context(self):
        """
        Before each LLM call during an active plan, inject a compact
        status message so the AI knows where it is in the plan.
        """
        if not self.plan_manager.current_plan:
            return
        if not self.plan_manager.current_plan.is_active:
            return

        context = self.plan_manager.to_llm_context()
        if context:
            self.messages.append({
                "role": "user",
                "content": f"[SYSTEM — Plan Status]\n{context}\n\nContinue executing the plan. Work on the next pending step.",
            })

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
            msg = {"role": "assistant", "content": full_response}
            self.messages.append(msg)
            self.history_manager.append_message(msg)
            ui.print()

        if tool_calls:
            tc_msg = {
                "role": "assistant",
                "tool_calls": tool_calls,
                "content": full_response or None
            }
            self.messages.append(tc_msg)
            self.history_manager.append_message(tc_msg)
            
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

                # ── Plan Approval Gate (Feature 4) ──
                if name == "create_plan" and self.plan_manager.current_plan:
                    self._handle_plan_approval_gate()

                # ── Plan Step Tracking (Feature 4) ──
                if name == "update_plan" and self.plan_manager.current_plan:
                    ui.print_plan(self.plan_manager.current_plan)

                # ── Plan Step Auto-Advance ──
                if self.plan_manager.current_plan and self.plan_manager.current_plan.is_active:
                    self._auto_advance_plan_step(name, result)

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

            # If plan was rejected, don't recurse — stop the agent loop
            if (self.plan_manager.current_plan 
                    and self.plan_manager.current_plan.status == PlanStatus.REJECTED):
                self.messages.append({
                    "role": "user",
                    "content": "[SYSTEM] The user rejected the proposed plan. Ask the user how they would like to proceed instead.",
                })
                next_usage = self._process_ai_response(tools, handlers)
                if next_usage and usage:
                    usage["prompt"] += next_usage["prompt"]
                    usage["completion"] += next_usage["completion"]
                    usage["total"] += next_usage["total"]
                elif next_usage:
                    usage = next_usage
                return usage

            # Recurse and accumulate usage
            next_usage = self._process_ai_response(tools, handlers)
            if next_usage and usage:
                usage["prompt"] += next_usage["prompt"]
                usage["completion"] += next_usage["completion"]
                usage["total"] += next_usage["total"]
            elif next_usage:
                usage = next_usage
                
        return usage

    # ── Plan Approval Gate ────────────────────────────────────────────────

    def _handle_plan_approval_gate(self):
        """
        After create_plan is called, show the plan and wait for approval.
        Auto-approved read-only plans skip the prompt.
        """
        plan = self.plan_manager.current_plan
        ui.print()
        ui.print_plan(plan)

        if plan.status == PlanStatus.AUTO_APPROVED:
            ui.print("[bold green]✅ Plan auto-approved (read-only operations only).[/bold green]\n")
            return

        # Interactive approval
        response = ui.prompt_plan_approval()

        if response == "y":
            self.plan_manager.approve()
            ui.print("[bold green]✅ Plan approved! Starting execution...[/bold green]\n")
        elif response == "e":
            # Enter interactive edit mode, then re-prompt
            self._interactive_plan_edit()
            # After editing, mark as approved (user has seen the final version)
            self.plan_manager.approve()
            ui.print("[bold green]✅ Modified plan approved! Starting execution...[/bold green]\n")
        else:
            self.plan_manager.reject()
            ui.print("[bold red]❌ Plan rejected by user.[/bold red]\n")

    def _auto_advance_plan_step(self, tool_name: str, result: str):
        """
        Automatically advance plan steps based on tool execution.
        Starts the next pending step if none is in progress.
        """
        plan = self.plan_manager.current_plan
        if not plan or not plan.is_active:
            return

        # Skip plan-management tools themselves
        if tool_name in ("create_plan", "update_plan"):
            return

        current_step = self.plan_manager.get_current_step()
        if not current_step:
            return

        # If no step is in_progress, start the next pending one
        if current_step.status == StepStatus.PENDING:
            self.plan_manager.start_step(current_step.index)
            ui.print_plan_step_update(
                current_step.index,
                current_step.description,
                "in_progress",
            )

    def _add_tool_result(self, tool_call_id, name, result):
        msg = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": result
        }
        self.messages.append(msg)
        self.history_manager.append_message(msg)
