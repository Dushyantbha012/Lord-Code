"""
run_command tool — Executes shell commands with safety checks and timeouts.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from src.tools.base import BaseTool, RiskLevel, ToolResult


# Maximum output lines before truncation
MAX_OUTPUT_LINES = 200
KEEP_FIRST = 100
KEEP_LAST = 50


class RunCommandTool(BaseTool):
    """Execute a shell command in the project directory."""

    def __init__(self, working_dir: str, timeout: int = 30) -> None:
        self._working_dir = Path(working_dir).resolve()
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "run_command"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command in the project directory and return its output. "
            "Use this for running tests, installing packages, checking git status, "
            "linting, or any other shell operation. The command runs with a timeout "
            f"of {self._timeout} seconds. Prefer non-destructive commands when possible."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                },
            },
            "required": ["command"],
        }

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.DANGEROUS

    def _truncate_output(self, output: str) -> tuple[str, bool]:
        """Truncate output if too long. Returns (output, was_truncated)."""
        lines = output.splitlines()
        if len(lines) <= MAX_OUTPUT_LINES:
            return output, False

        first = lines[:KEEP_FIRST]
        last = lines[-KEEP_LAST:]
        omitted = len(lines) - KEEP_FIRST - KEEP_LAST
        truncated = (
            "\n".join(first)
            + f"\n\n[... {omitted} lines omitted ...]\n\n"
            + "\n".join(last)
        )
        return truncated, True

    async def execute(self, command: str, **kwargs: Any) -> ToolResult:
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._working_dir),
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Failed to start command: {e}",
                display_output=f"❌ Failed to start: {e}",
            )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()  # Clean up
            return ToolResult(
                success=False,
                output=f"Command timed out after {self._timeout}s: {command}",
                display_output=f"⏱️ Timed out after {self._timeout}s",
                metadata={"exit_code": -1, "timed_out": True},
            )

        # Decode output
        stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
        exit_code = process.returncode or 0

        # Combine output
        combined = ""
        if stdout:
            combined += stdout
        if stderr:
            if combined:
                combined += "\n--- STDERR ---\n"
            combined += stderr

        if not combined.strip():
            combined = "(no output)"

        # Truncate if needed
        combined, was_truncated = self._truncate_output(combined)

        success = exit_code == 0
        status = "✅" if success else "❌"

        return ToolResult(
            success=success,
            output=f"Exit code: {exit_code}\n\n{combined}",
            display_output=f"{status} Command exited with code {exit_code}",
            metadata={
                "exit_code": exit_code,
                "command": command,
                "truncated": was_truncated,
            },
        )
