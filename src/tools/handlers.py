import subprocess
import os
import glob

def read_file(path: str) -> str:
    try:
        with open(path, 'r') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_file(path: str, content: str) -> str:
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

def execute_command(command: str) -> str:
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = result.stdout if result.stdout else ""
        error = result.stderr if result.stderr else ""
        return f"STDOUT:\n{output}\nSTDERR:\n{error}\nExit Code: {result.returncode}"
    except Exception as e:
        return f"Error executing command: {str(e)}"

def list_files(path: str) -> str:
    try:
        files = os.listdir(path)
        return "\n".join(files)
    except Exception as e:
        return f"Error listing files: {str(e)}"

def grep_search(pattern: str, path: str) -> str:
    try:
        # Use simple recursive search if it's a directory, else search file
        if os.path.isdir(path):
            cmd = f"grep -rE \"{pattern}\" \"{path}\""
        else:
            cmd = f"grep -E \"{pattern}\" \"{path}\""
        return execute_command(cmd)
    except Exception as e:
        return f"Error in grep search: {str(e)}"

# Registry for easy dispatch
TOOL_HANDLERS = {
    "read_file": read_file,
    "write_file": write_file,
    "execute_command": execute_command,
    "list_files": list_files,
    "grep_search": grep_search
}
