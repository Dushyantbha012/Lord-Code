"""
StorageManager — Centralized .lord-code/ directory manager.

Creates and manages the .lord-code/ directory structure inside the TARGET project
(the codebase Lord Code is working on), providing path helpers and metadata.
"""

import json
import os
from datetime import datetime
from typing import Optional


# The directory name used inside every target project
LORD_CODE_DIR = ".lord-code"

# Subdirectories
SUBDIRS = ["history", "plans", "configs"]


class StorageManager:
    """
    Manages the .lord-code/ directory structure inside the target project.

    Usage:
        storage = StorageManager("/path/to/target/project")
        plan_path = storage.get_path("plans", "current_plan.json")
        history_dir = storage.get_dir("history")
    """

    def __init__(self, working_dir: str):
        """
        Initialize the storage manager for the given target project directory.

        Args:
            working_dir: The root directory of the project Lord Code is working on.
        """
        self.working_dir = os.path.abspath(working_dir)
        self.root = os.path.join(self.working_dir, LORD_CODE_DIR)

        # Create the directory structure
        self.ensure_dirs()

        # Load or create metadata
        self._meta = self._load_or_create_meta()

    def ensure_dirs(self):
        """Create .lord-code/ and all subdirectories if they don't exist."""
        os.makedirs(self.root, exist_ok=True)
        for subdir in SUBDIRS:
            os.makedirs(os.path.join(self.root, subdir), exist_ok=True)

    def get_path(self, component: str, filename: str) -> str:
        """
        Get the absolute path for a file inside a .lord-code component.

        Args:
            component: Subdirectory name (e.g., 'history', 'plans', 'configs')
            filename: File name within that component

        Returns:
            Absolute path string

        Example:
            storage.get_path("plans", "current_plan.json")
            → "/path/to/project/.lord-code/plans/current_plan.json"
        """
        return os.path.join(self.root, component, filename)

    def get_dir(self, component: str) -> str:
        """
        Get the absolute path for a component directory.

        Args:
            component: Subdirectory name (e.g., 'history', 'plans', 'configs')

        Returns:
            Absolute path to the directory
        """
        return os.path.join(self.root, component)

    @property
    def meta(self) -> dict:
        """Return the current metadata."""
        return self._meta

    def _meta_path(self) -> str:
        return os.path.join(self.root, "meta.json")

    def _load_or_create_meta(self) -> dict:
        """Load meta.json or create it on first run."""
        path = self._meta_path()
        if os.path.isfile(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass  # Corrupted, recreate

        meta = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "project_dir": self.working_dir,
            "lord_code_data": True,
        }
        self._save_meta(meta)
        return meta

    def _save_meta(self, meta: dict):
        """Write meta.json."""
        try:
            with open(self._meta_path(), "w") as f:
                json.dump(meta, f, indent=2)
        except Exception:
            pass

    def get_stats(self) -> dict:
        """
        Get storage statistics for display.

        Returns:
            Dict with session_count, config_snapshot_count, has_active_plan
        """
        stats = {
            "session_count": 0,
            "config_snapshot_count": 0,
            "has_active_plan": False,
        }

        # Count session files
        history_dir = self.get_dir("history")
        sessions_file = os.path.join(history_dir, "sessions.json")
        if os.path.isfile(sessions_file):
            try:
                with open(sessions_file, "r") as f:
                    sessions = json.load(f)
                stats["session_count"] = len(sessions)
            except Exception:
                pass

        # Count config snapshots
        configs_dir = self.get_dir("configs")
        snapshots_file = os.path.join(configs_dir, "snapshots.json")
        if os.path.isfile(snapshots_file):
            try:
                with open(snapshots_file, "r") as f:
                    snapshots = json.load(f)
                stats["config_snapshot_count"] = len(snapshots)
            except Exception:
                pass

        # Check for active plan
        plan_file = self.get_path("plans", "current_plan.json")
        stats["has_active_plan"] = os.path.isfile(plan_file)

        return stats
