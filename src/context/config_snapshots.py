"""
ConfigSnapshotManager — Save/restore codebase configuration snapshots.

Lets users save named snapshots of their current Lord Code configuration
(model, token budgets, custom instructions, ignored paths, etc.) inside
the target project's .lord-code/configs/ directory. Useful for switching
between different working modes (e.g., "fast-iteration" vs "thorough-review").
"""

import json
import os
import shutil
from datetime import datetime
from typing import List, Dict, Optional, Any


class ConfigSnapshotManager:
    """
    Manages named configuration snapshots.

    Usage:
        snapshots = ConfigSnapshotManager(storage)
        snapshots.save("fast-dev", project_config, model_id="llama-3.1-8b-instant")
        snapshots.list_snapshots()
        config_dict = snapshots.load("fast-dev")
    """

    def __init__(self, storage):
        """
        Args:
            storage: A StorageManager instance
        """
        self.storage = storage
        self.configs_dir = storage.get_dir("configs")
        self.index_file = os.path.join(self.configs_dir, "snapshots.json")

    # ── Save / Load ───────────────────────────────────────────────────────

    def save(self, name: str, project_config, model_id: str = "",
             reasoning_enabled: bool = False) -> str:
        """
        Save the current configuration as a named snapshot.

        Args:
            name: Snapshot name (used as filename, sanitized)
            project_config: ProjectConfig instance
            model_id: Current active model ID
            reasoning_enabled: Whether reasoning mode is on

        Returns:
            Success/error message
        """
        safe_name = self._sanitize_name(name)
        if not safe_name:
            return "Error: Invalid snapshot name."

        try:
            # Build snapshot data
            snapshot_data = {
                "name": name,
                "saved_at": datetime.now().isoformat(),
                "model": model_id,
                "reasoning_enabled": reasoning_enabled,
                "config": project_config.to_dict() if hasattr(project_config, 'to_dict') else {},
            }

            # Write the snapshot file
            filepath = os.path.join(self.configs_dir, f"{safe_name}.json")
            with open(filepath, "w") as f:
                json.dump(snapshot_data, f, indent=2)

            # Update index
            index = self._load_index()
            index[name] = {
                "file": f"{safe_name}.json",
                "saved_at": snapshot_data["saved_at"],
                "model": model_id,
            }
            self._save_index(index)

            return f"✅ Configuration saved as '{name}'"

        except Exception as e:
            return f"Error saving snapshot: {str(e)}"

    def load(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Load a named snapshot.

        Args:
            name: Snapshot name

        Returns:
            Snapshot data dict, or None if not found
        """
        index = self._load_index()
        if name not in index:
            return None

        filepath = os.path.join(self.configs_dir, index[name]["file"])
        if not os.path.isfile(filepath):
            return None

        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception:
            return None

    # ── List / Delete ─────────────────────────────────────────────────────

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """
        List all saved snapshots.

        Returns:
            List of dicts with name, saved_at, model
        """
        index = self._load_index()
        result = []
        for name, meta in index.items():
            result.append({
                "name": name,
                "saved_at": meta.get("saved_at", "unknown"),
                "model": meta.get("model", "unknown"),
            })
        return result

    def delete(self, name: str) -> str:
        """
        Delete a saved snapshot.

        Args:
            name: Snapshot name

        Returns:
            Success/error message
        """
        index = self._load_index()
        if name not in index:
            return f"Error: Snapshot '{name}' not found."

        # Delete the file
        filepath = os.path.join(self.configs_dir, index[name]["file"])
        try:
            if os.path.isfile(filepath):
                os.remove(filepath)
        except Exception:
            pass

        # Remove from index
        del index[name]
        self._save_index(index)
        return f"🗑️ Snapshot '{name}' deleted."

    # ── Export ─────────────────────────────────────────────────────────────

    def export_snapshot(self, name: str) -> str:
        """
        Export a snapshot to the project root as a .lordcode.yaml file.
        This lets users version-control their preferred configuration.

        Args:
            name: Snapshot name

        Returns:
            Success/error message
        """
        data = self.load(name)
        if not data:
            return f"Error: Snapshot '{name}' not found."

        try:
            config_data = data.get("config", {})
            # Add model to config
            if data.get("model"):
                config_data["model"] = data["model"]

            # Write as YAML if pyyaml is available, else JSON
            try:
                import yaml
                dest = os.path.join(self.storage.working_dir, ".lordcode.yaml")
                with open(dest, "w") as f:
                    yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
                return f"📤 Exported '{name}' to .lordcode.yaml"
            except ImportError:
                dest = os.path.join(self.storage.working_dir, ".lordcode.json")
                with open(dest, "w") as f:
                    json.dump(config_data, f, indent=2)
                return f"📤 Exported '{name}' to .lordcode.json (install pyyaml for .yaml export)"

        except Exception as e:
            return f"Error exporting snapshot: {str(e)}"

    # ── Internal ──────────────────────────────────────────────────────────

    def _load_index(self) -> Dict[str, Any]:
        """Load the snapshots.json index."""
        if not os.path.isfile(self.index_file):
            return {}
        try:
            with open(self.index_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_index(self, index: Dict[str, Any]) -> None:
        """Write the snapshots.json index."""
        try:
            with open(self.index_file, "w") as f:
                json.dump(index, f, indent=2)
        except Exception:
            pass

    def _sanitize_name(self, name: str) -> str:
        """Sanitize a snapshot name for use as a filename."""
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name.strip())
        return safe[:50] if safe else ""
