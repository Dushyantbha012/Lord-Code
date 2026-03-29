"""
Multi-Step Planning System for Lord Code.

Provides structured plan creation, approval gating, step-by-step execution
tracking, mid-execution modification, and disk persistence.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


# ── Status Enums ──────────────────────────────────────────────────────────────

class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStatus(str, Enum):
    PENDING_APPROVAL = "pending_approval"
    AUTO_APPROVED = "auto_approved"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    MODIFIED = "modified"


# Tools that are considered read-only (safe to auto-approve)
READ_ONLY_TOOLS = {
    "read_file", "list_files", "grep_search", "find_files",
    "search_in_files", "find_definition", "get_git_diff",
    "get_git_log", "git_status", "git_diff_ref",
}


# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class PlanStep:
    index: int
    description: str
    status: StepStatus = StepStatus.PENDING
    result: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "description": self.description,
            "status": self.status.value,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlanStep":
        return cls(
            index=data["index"],
            description=data["description"],
            status=StepStatus(data["status"]),
            result=data.get("result"),
        )


@dataclass
class Plan:
    title: str
    steps: List[PlanStep] = field(default_factory=list)
    status: PlanStatus = PlanStatus.PENDING_APPROVAL
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status.value,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        plan = cls(
            title=data["title"],
            status=PlanStatus(data["status"]),
            created_at=data.get("created_at", datetime.now().isoformat()),
            modified_at=data.get("modified_at"),
        )
        plan.steps = [PlanStep.from_dict(s) for s in data.get("steps", [])]
        return plan

    @property
    def is_active(self) -> bool:
        """Plan is active if it's approved/executing/modified."""
        return self.status in (
            PlanStatus.APPROVED,
            PlanStatus.AUTO_APPROVED,
            PlanStatus.EXECUTING,
            PlanStatus.MODIFIED,
        )

    @property
    def is_complete(self) -> bool:
        """All steps are done, failed, or skipped."""
        if not self.steps:
            return False
        return all(
            s.status in (StepStatus.DONE, StepStatus.FAILED, StepStatus.SKIPPED)
            for s in self.steps
        )

    @property
    def progress(self) -> str:
        """e.g. '3/7 steps done'"""
        done = sum(1 for s in self.steps if s.status == StepStatus.DONE)
        return f"{done}/{len(self.steps)} steps done"


# ── Plan Manager ──────────────────────────────────────────────────────────────

class PlanManager:
    """
    Stateful controller for the active plan.
    Handles creation, approval, step lifecycle, modification, and persistence.
    """

    # New path inside .lord-code/
    PERSISTENCE_FILE = "current_plan.json"
    # Old path (for migration)
    LEGACY_FILE = ".lordcode_plan.json"

    def __init__(self, working_dir: str, storage=None):
        """
        Args:
            working_dir: Target project directory
            storage: Optional StorageManager instance. If provided, uses
                     .lord-code/plans/ for persistence. Otherwise falls back
                     to the old root-level file.
        """
        self.working_dir = working_dir
        self.storage = storage
        self.current_plan: Optional[Plan] = None
        self._history: List[Plan] = []

        # Auto-migrate old persistence file if .lord-code is available
        if self.storage:
            self._migrate_legacy_file()

        # Try to load a persisted plan
        self._load_from_disk()

    # ── Creation ──────────────────────────────────────────────────────────

    def create_plan(self, title: str, steps: List[str]) -> Plan:
        """
        Create a new plan. If a plan already exists, archive it.
        Returns the new plan.
        """
        if self.current_plan:
            self._history.append(self.current_plan)

        plan_steps = [
            PlanStep(index=i, description=desc)
            for i, desc in enumerate(steps)
        ]
        self.current_plan = Plan(title=title, steps=plan_steps)

        # Check if this is a read-only plan (auto-approve)
        if self._is_read_only_plan():
            self.current_plan.status = PlanStatus.AUTO_APPROVED

        self._save_to_disk()
        return self.current_plan

    def _is_read_only_plan(self) -> bool:
        """
        Heuristic: if all step descriptions only reference read-only operations,
        auto-approve. We check for keywords associated with write operations.
        """
        write_keywords = [
            "write", "create", "edit", "modify", "delete", "remove",
            "install", "run", "execute", "commit", "push", "deploy",
            "update", "change", "refactor", "fix", "add", "implement",
            "build", "compile", "migrate",
        ]
        for step in self.current_plan.steps:
            desc_lower = step.description.lower()
            if any(kw in desc_lower for kw in write_keywords):
                return False
        return True

    # ── Approval ──────────────────────────────────────────────────────────

    def approve(self) -> str:
        if not self.current_plan:
            return "No plan to approve."
        if self.current_plan.status != PlanStatus.PENDING_APPROVAL:
            return f"Plan is already {self.current_plan.status.value}."
        self.current_plan.status = PlanStatus.APPROVED
        self._save_to_disk()
        return "✅ Plan approved! Execution will begin."

    def reject(self) -> str:
        if not self.current_plan:
            return "No plan to reject."
        self.current_plan.status = PlanStatus.REJECTED
        self._save_to_disk()
        return "❌ Plan rejected."

    def needs_approval(self) -> bool:
        """Check if the current plan is waiting for user approval."""
        return (
            self.current_plan is not None
            and self.current_plan.status == PlanStatus.PENDING_APPROVAL
        )

    # ── Step Lifecycle ────────────────────────────────────────────────────

    def get_current_step(self) -> Optional[PlanStep]:
        """Get the next pending step, or the in-progress step."""
        if not self.current_plan or not self.current_plan.is_active:
            return None
        for step in self.current_plan.steps:
            if step.status == StepStatus.IN_PROGRESS:
                return step
        for step in self.current_plan.steps:
            if step.status == StepStatus.PENDING:
                return step
        return None

    def start_step(self, idx: int) -> str:
        if not self.current_plan:
            return "No active plan."
        if idx < 0 or idx >= len(self.current_plan.steps):
            return f"Invalid step index: {idx}"

        step = self.current_plan.steps[idx]
        step.status = StepStatus.IN_PROGRESS
        self.current_plan.status = PlanStatus.EXECUTING
        self._save_to_disk()
        return f"🔄 Started step {idx}: {step.description}"

    def complete_step(self, idx: int, result: str = "") -> str:
        if not self.current_plan:
            return "No active plan."
        if idx < 0 or idx >= len(self.current_plan.steps):
            return f"Invalid step index: {idx}"

        step = self.current_plan.steps[idx]
        step.status = StepStatus.DONE
        step.result = result

        # Check if plan is now complete
        if self.current_plan.is_complete:
            self.current_plan.status = PlanStatus.COMPLETED

        self._save_to_disk()
        return f"✅ Completed step {idx}: {step.description}"

    def fail_step(self, idx: int, error: str = "") -> str:
        if not self.current_plan:
            return "No active plan."
        if idx < 0 or idx >= len(self.current_plan.steps):
            return f"Invalid step index: {idx}"

        step = self.current_plan.steps[idx]
        step.status = StepStatus.FAILED
        step.result = error
        self._save_to_disk()
        return f"❌ Failed step {idx}: {step.description} — {error}"

    def skip_step(self, idx: int) -> str:
        if not self.current_plan:
            return "No active plan."
        if idx < 0 or idx >= len(self.current_plan.steps):
            return f"Invalid step index: {idx}"

        step = self.current_plan.steps[idx]
        step.status = StepStatus.SKIPPED
        step.result = "Skipped by user"

        # Check if plan is now complete
        if self.current_plan.is_complete:
            self.current_plan.status = PlanStatus.COMPLETED

        self._save_to_disk()
        return f"⏭️ Skipped step {idx}: {step.description}"

    # ── Modification ──────────────────────────────────────────────────────

    def add_step(self, description: str, at_index: Optional[int] = None) -> str:
        """Add a new step. Inserts at `at_index` or appends to end."""
        if not self.current_plan:
            return "No active plan."

        if at_index is not None and 0 <= at_index <= len(self.current_plan.steps):
            new_step = PlanStep(index=at_index, description=description)
            self.current_plan.steps.insert(at_index, new_step)
        else:
            new_step = PlanStep(index=len(self.current_plan.steps), description=description)
            self.current_plan.steps.append(new_step)

        # Re-index all steps
        self._reindex_steps()
        self.current_plan.modified_at = datetime.now().isoformat()
        self.current_plan.status = PlanStatus.MODIFIED
        self._save_to_disk()
        return f"➕ Added step: {description}"

    def remove_step(self, idx: int) -> str:
        """Remove a step by index."""
        if not self.current_plan:
            return "No active plan."
        if idx < 0 or idx >= len(self.current_plan.steps):
            return f"Invalid step index: {idx}"

        removed = self.current_plan.steps.pop(idx)
        self._reindex_steps()
        self.current_plan.modified_at = datetime.now().isoformat()
        self.current_plan.status = PlanStatus.MODIFIED
        self._save_to_disk()
        return f"➖ Removed step: {removed.description}"

    def modify_step(self, idx: int, new_description: str) -> str:
        """Change a step's description."""
        if not self.current_plan:
            return "No active plan."
        if idx < 0 or idx >= len(self.current_plan.steps):
            return f"Invalid step index: {idx}"

        old = self.current_plan.steps[idx].description
        self.current_plan.steps[idx].description = new_description
        self.current_plan.modified_at = datetime.now().isoformat()
        self.current_plan.status = PlanStatus.MODIFIED
        self._save_to_disk()
        return f"✏️ Modified step {idx}: '{old}' → '{new_description}'"

    def _reindex_steps(self):
        """Re-number step indices after insert/remove."""
        for i, step in enumerate(self.current_plan.steps):
            step.index = i

    # ── Context for LLM ───────────────────────────────────────────────────

    def to_llm_context(self) -> str:
        """
        Compact plan representation to inject into messages.
        Keeps token usage low.
        """
        if not self.current_plan:
            return ""

        plan = self.current_plan
        status_icons = {
            StepStatus.PENDING: "⏳",
            StepStatus.IN_PROGRESS: "🔄",
            StepStatus.DONE: "✅",
            StepStatus.FAILED: "❌",
            StepStatus.SKIPPED: "⏭️",
        }

        lines = [f"[PLAN: {plan.title}] ({plan.progress})"]
        for step in plan.steps:
            icon = status_icons.get(step.status, "?")
            result_note = ""
            if step.result and step.status in (StepStatus.DONE, StepStatus.FAILED):
                # Truncate result for context
                short = step.result[:100] + "..." if len(step.result) > 100 else step.result
                result_note = f" → {short}"
            lines.append(f"  {icon} {step.index}. {step.description}{result_note}")

        current = self.get_current_step()
        if current:
            lines.append(f"  >> Current: Step {current.index}")
        elif plan.is_complete:
            lines.append("  >> Plan complete.")

        return "\n".join(lines)

    def get_summary(self) -> str:
        """Human-readable rich summary (used by /plan command)."""
        if not self.current_plan:
            return "No active plan."
        return self.to_llm_context()

    # ── Persistence ───────────────────────────────────────────────────────

    def _persistence_path(self) -> str:
        """Get the plan persistence file path."""
        if self.storage:
            return self.storage.get_path("plans", self.PERSISTENCE_FILE)
        # Fallback: old root-level path
        return os.path.join(self.working_dir, self.LEGACY_FILE)

    def _save_to_disk(self):
        """Save current plan to .lord-code/plans/current_plan.json."""
        if not self.current_plan:
            return
        try:
            path = self._persistence_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = {
                "current_plan": self.current_plan.to_dict(),
                "history_count": len(self._history),
            }
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass  # Non-critical, silently ignore

    def _load_from_disk(self):
        """Load a persisted plan if one exists."""
        path = self._persistence_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            if "current_plan" in data:
                self.current_plan = Plan.from_dict(data["current_plan"])
        except Exception:
            pass  # Corrupted file, start fresh

    def _migrate_legacy_file(self):
        """Migrate old .lordcode_plan.json from project root to .lord-code/plans/."""
        legacy_path = os.path.join(self.working_dir, self.LEGACY_FILE)
        if not os.path.isfile(legacy_path):
            return

        new_path = self._persistence_path()
        try:
            # Only migrate if new path doesn't already exist
            if not os.path.isfile(new_path):
                import shutil
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                shutil.move(legacy_path, new_path)
            else:
                # New path exists, just clean up old file
                os.remove(legacy_path)
        except Exception:
            pass  # Non-critical

    def clear(self):
        """Clear the current plan and remove persistence file."""
        if self.current_plan:
            self._history.append(self.current_plan)
        self.current_plan = None
        try:
            path = self._persistence_path()
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
