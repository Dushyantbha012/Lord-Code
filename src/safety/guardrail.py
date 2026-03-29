import os
from pathlib import Path
from src.tools.utils import find_project_root


class SafetyGuard:
    """Centralized safety validator for the Lord-Code CLI."""

    def __init__(self):
        self.project_root = find_project_root()
        # Blacklisted commands that are strictly forbidden.
        self.blacklist = [
            "rm -rf /", "rm -rf *", "mkfs", "dd if=", "> /dev/", "format ", 
            "chown ", "chmod 777", "chmod -R 777", "shred "
        ]
        # Destructive keywords that trigger mandatory user approval.
        self.destructive_keywords = ["rm ", "rmdir ", "del ", "erase ", "mv ", "cp "]

    def is_path_safe(self, path: str) -> bool:
        """Check if a path is within the project root and not sensitive (e.g., .env)."""
        absolute_path = os.path.abspath(os.path.join(self.project_root, path))
        
        # 1. Sandbox Check
        if not absolute_path.startswith(self.project_root):
            return False
        
        # 2. Sensitive File Check
        filename = os.path.basename(absolute_path)
        if filename.startswith(".env"):
            return False
            
        return True

    def get_command_safety(self, command: str) -> tuple[bool, str]:
        """
        Check if a shell command is safe.
        Returns (is_safe, risk_level). Risk levels: 'blocked', 'high', 'low'
        """
        cmd_clean = command.strip().lower()

        # 1. Blocklist Check (Strictly Forbidden)
        for forbidden in self.blacklist:
            if forbidden in cmd_clean:
                return False, "blocked"

        # 2. Destructive Keyword Check (Requires Approval)
        for keyword in self.destructive_keywords:
            if keyword in cmd_clean:
                return True, "high"

        # 3. Default (Low-Risk)
        return True, "low"

    def get_tool_risk(self, tool_name: str, arguments: dict) -> str:
        """Evaluate the overall risk level of a tool call."""
        if tool_name == "run_command":
            command = arguments.get("command", "")
            is_safe, risk = self.get_command_safety(command)
            if not is_safe: return "blocked"
            return risk
            
        if tool_name == "write_file":
            path = arguments.get("path", "")
            if not self.is_path_safe(path): return "blocked"
            return "high" # Writing files is always considered high risk by default.
            
        if tool_name == "read_file" or tool_name == "list_dir":
            path = arguments.get("path", ".")
            if not self.is_path_safe(path): return "blocked"
            return "low"
            
        return "low"

# Singleton instance
safety_guard = SafetyGuard()
