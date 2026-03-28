import os
import re

DANGEROUS_COMMANDS = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+\*",
    r"format\s+",
    r"mkfs",
    r"dd\s+",
    r"> /dev/sd",
    r":\(\)\{ :\|:& \};:", # Fork bomb
]

def is_command_safe(command: str) -> bool:
    for pattern in DANGEROUS_COMMANDS:
        if re.search(pattern, command):
            return False
    return True

def is_path_safe(path: str, root_dir: str) -> bool:
    abs_root = os.path.abspath(root_dir)
    # Expand ~ and normalize the path
    expanded_path = os.path.expanduser(path)
    if os.path.isabs(expanded_path):
        abs_path = os.path.abspath(expanded_path)
    else:
        abs_path = os.path.abspath(os.path.join(root_dir, expanded_path))
    
    return abs_path.startswith(abs_root)

def needs_confirmation(tool_name: str) -> bool:
    return tool_name in ["write_file", "execute_command"]
