"""
Sub-Agent / Parallel Tool Execution Engine.

Classifies tool calls into parallel-safe vs sequential-only batches,
executes parallel tasks via ThreadPoolExecutor with real-time progress
reporting, and runs sequential tasks in order with full post-hook support.
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable, Tuple


# ── Tool Classification ──────────────────────────────────────────────────────

# Read-only tools that can ALWAYS run in parallel (no side effects)
ALWAYS_PARALLEL_SAFE = frozenset({
    "read_file",
    "find_files",
    "search_in_files",
    "find_definition",
    "grep_search",
    "list_files",
    "get_git_diff",
    "get_git_log",
    "git_status",
    "git_diff_ref",
})

# Tools that must ALWAYS run sequentially (state mutations, ordering matters)
ALWAYS_SEQUENTIAL = frozenset({
    "execute_command",
    "git_commit",
    "git_create_branch",
    "git_stash",
    "git_unstash",
    "run_tests",
    "create_plan",
    "update_plan",
})

# Write tools that CAN be parallelized if targeting different files
FILE_WRITE_TOOLS = frozenset({
    "write_file",
    "edit_file",
})


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ToolTask:
    """Represents a single tool call ready for execution."""
    task_id: int
    tool_call_id: str       # Original TC id from the LLM
    name: str               # Tool name
    args: Dict[str, Any]    # Parsed arguments
    handler: Callable       # The handler function to call
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    duration: float = 0.0
    target_file: Optional[str] = None  # For write tools — used for dedup


@dataclass
class ParallelResult:
    """Result of a parallel/sequential execution batch."""
    tasks: List[ToolTask]
    total_duration: float = 0.0
    parallel_count: int = 0
    sequential_count: int = 0


class ParallelExecutor:
    """
    Executes tool calls with automatic parallelism for independent operations.

    Usage:
        executor = ParallelExecutor(max_workers=4)
        parallel, sequential = executor.classify(tasks)
        results = executor.execute_parallel(parallel, on_progress=callback)
        for task in sequential:
            executor.execute_one(task)
    """

    MAX_WORKERS = 4

    def __init__(self, max_workers: int = MAX_WORKERS):
        self.max_workers = max_workers

    # ── Classification ────────────────────────────────────────────────────

    def classify(self, tasks: List[ToolTask]) -> Tuple[List[ToolTask], List[ToolTask]]:
        """
        Split tasks into parallel-safe and sequential-only batches.

        Rules:
        1. Tools in ALWAYS_PARALLEL_SAFE → parallel
        2. Tools in ALWAYS_SEQUENTIAL → sequential
        3. File write tools (write_file, edit_file):
           - Different target files → parallel
           - Same target file → sequential (preserve ordering)

        Returns:
            (parallel_tasks, sequential_tasks)
        """
        parallel = []
        sequential = []
        seen_write_files = set()  # Track files being written to

        for task in tasks:
            if task.name in ALWAYS_PARALLEL_SAFE:
                parallel.append(task)

            elif task.name in ALWAYS_SEQUENTIAL:
                sequential.append(task)

            elif task.name in FILE_WRITE_TOOLS:
                # Extract target file path
                target = task.args.get("path", "")
                task.target_file = target

                if target and target not in seen_write_files:
                    # First write to this file — can parallelize
                    seen_write_files.add(target)
                    parallel.append(task)
                else:
                    # Same file being written again — must be sequential
                    sequential.append(task)

            else:
                # Unknown tool — default to sequential (safe)
                sequential.append(task)

        return parallel, sequential

    # ── Execution ─────────────────────────────────────────────────────────

    def execute_parallel(
        self,
        tasks: List[ToolTask],
        on_progress: Optional[Callable[[ToolTask], None]] = None,
    ) -> ParallelResult:
        """
        Execute tasks in parallel using ThreadPoolExecutor.

        Args:
            tasks: List of ToolTasks to execute concurrently
            on_progress: Callback fired when a task starts/completes/fails.
                         Receives the updated ToolTask.

        Returns:
            ParallelResult with all completed tasks
        """
        if not tasks:
            return ParallelResult(tasks=[], parallel_count=0)

        # For a single task, no need for thread overhead
        if len(tasks) == 1:
            self.execute_one(tasks[0], on_progress)
            return ParallelResult(
                tasks=tasks,
                total_duration=tasks[0].duration,
                parallel_count=1,
            )

        start_time = time.time()
        workers = min(len(tasks), self.max_workers)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_to_task: Dict[Future, ToolTask] = {}

            for task in tasks:
                task.status = TaskStatus.RUNNING
                if on_progress:
                    on_progress(task)

                future = pool.submit(self._run_task, task)
                future_to_task[future] = task

            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    future.result()  # Raises if the task raised
                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    task.result = f"Error: {str(e)}"

                if on_progress:
                    on_progress(task)

        total_duration = time.time() - start_time

        return ParallelResult(
            tasks=tasks,
            total_duration=total_duration,
            parallel_count=len(tasks),
        )

    def execute_one(
        self,
        task: ToolTask,
        on_progress: Optional[Callable[[ToolTask], None]] = None,
    ) -> None:
        """
        Execute a single task synchronously.

        Args:
            task: The ToolTask to execute
            on_progress: Optional callback for status updates
        """
        task.status = TaskStatus.RUNNING
        if on_progress:
            on_progress(task)

        self._run_task(task)

        if on_progress:
            on_progress(task)

    # ── Internal ──────────────────────────────────────────────────────────

    def _run_task(self, task: ToolTask) -> None:
        """Execute a single tool task and update its status/result."""
        start = time.time()
        try:
            result = task.handler(**task.args)
            task.result = result
            task.status = TaskStatus.DONE
        except Exception as e:
            task.result = f"Error: {str(e)}"
            task.error = str(e)
            task.status = TaskStatus.FAILED
        finally:
            task.duration = time.time() - start


def build_tasks(
    tool_calls: List[Dict],
    args_list: List[Dict],
    handlers: Dict[str, Callable],
) -> List[ToolTask]:
    """
    Convert raw tool call dicts + parsed args into ToolTask objects.

    Args:
        tool_calls: List of tool call dicts from the LLM response
        args_list: List of parsed argument dicts (same order)
        handlers: TOOL_HANDLERS registry

    Returns:
        List of ToolTask objects ready for classification and execution
    """
    tasks = []
    for i, (tc, args) in enumerate(zip(tool_calls, args_list)):
        name = tc["function"]["name"]
        handler = handlers.get(name)
        if not handler:
            # Create a dummy task that will return an error
            task = ToolTask(
                task_id=i,
                tool_call_id=tc["id"],
                name=name,
                args=args,
                handler=lambda **kw: f"Error: Tool {name} not found.",
                status=TaskStatus.FAILED,
                result=f"Error: Tool {name} not found.",
            )
        else:
            task = ToolTask(
                task_id=i,
                tool_call_id=tc["id"],
                name=name,
                args=args,
                handler=handler,
            )
        tasks.append(task)
    return tasks
