import os
import pytest
from src.cli.safety import is_command_safe, is_path_safe

def test_is_command_safe():
    # Safe commands
    assert is_command_safe("ls -la") is True
    assert is_command_safe("git status") is True
    assert is_command_safe("python3 src/main.py") is True
    
    # Dangerous commands
    assert is_command_safe("rm -rf /") is False
    assert is_command_safe("rm -rf *") is False
    assert is_command_safe("format C:") is False
    assert is_command_safe(":(){ :|:& };:") is False

def test_is_path_safe():
    root = "/Users/dushyantbhardwaj/Documents/Realestate/Claude-Code-Clone"
    
    # Safe paths
    assert is_path_safe("src/main.py", root) is True
    assert is_path_safe("./readme.md", root) is True
    assert is_path_safe(root + "/src/cli/safety.py", root) is True
    
    # Unsafe paths
    assert is_path_safe("../secret.txt", root) is False
    assert is_path_safe("/etc/passwd", root) is False
    assert is_path_safe("~/.ssh/id_rsa", root) is False
