"""
Test Execution Loop (Feature 3.3)

Auto-detects the project's test framework and runs tests.
Supports pytest, npm test, and cargo test.
"""

import os
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class TestResult:
    """Result of a test run."""
    success: bool
    output: str
    framework: str
    failed_count: int = 0


# ── Framework Detection ──

def _detect_framework(project_root: str) -> Optional[dict]:
    """
    Detect the test framework from project files.
    Returns dict with 'name' and 'command' or None.
    """
    # Python — pytest
    pytest_indicators = [
        "pytest.ini",
        "conftest.py",
        "setup.cfg",  # may have [tool:pytest]
    ]
    for indicator in pytest_indicators:
        if os.path.exists(os.path.join(project_root, indicator)):
            return {"name": "pytest", "base_cmd": ["python", "-m", "pytest"]}

    # Check pyproject.toml for pytest config
    pyproject = os.path.join(project_root, "pyproject.toml")
    if os.path.exists(pyproject):
        try:
            with open(pyproject, "r") as f:
                content = f.read()
            if "[tool.pytest" in content:
                return {"name": "pytest", "base_cmd": ["python", "-m", "pytest"]}
        except Exception:
            pass

    # Node.js — npm test
    pkg_json = os.path.join(project_root, "package.json")
    if os.path.exists(pkg_json):
        try:
            import json
            with open(pkg_json, "r") as f:
                pkg = json.load(f)
            if "scripts" in pkg and "test" in pkg["scripts"]:
                test_script = pkg["scripts"]["test"]
                # Skip placeholder scripts
                if test_script and "no test specified" not in test_script:
                    return {"name": "npm", "base_cmd": ["npm", "test", "--"]}
        except Exception:
            pass

    # Rust — cargo test
    if os.path.exists(os.path.join(project_root, "Cargo.toml")):
        return {"name": "cargo", "base_cmd": ["cargo", "test"]}

    # Go — go test
    if os.path.exists(os.path.join(project_root, "go.mod")):
        return {"name": "go", "base_cmd": ["go", "test", "./..."]}

    # Fallback: check if tests/ directory exists with Python files → assume pytest
    tests_dir = os.path.join(project_root, "tests")
    if os.path.isdir(tests_dir):
        py_tests = [f for f in os.listdir(tests_dir) if f.startswith("test_") and f.endswith(".py")]
        if py_tests:
            return {"name": "pytest", "base_cmd": ["python", "-m", "pytest"]}

    return None


def _parse_pytest_failures(output: str) -> int:
    """Extract the number of failures from pytest output."""
    import re
    # Match patterns like "1 failed" or "3 failed, 2 passed"
    match = re.search(r"(\d+) failed", output)
    if match:
        return int(match.group(1))
    return 0


def _parse_npm_failures(output: str) -> int:
    """Extract failure count from npm test output."""
    import re
    # Jest: "Tests: X failed"
    match = re.search(r"Tests:\s+(\d+) failed", output)
    if match:
        return int(match.group(1))
    # Mocha: "X failing"
    match = re.search(r"(\d+) failing", output)
    if match:
        return int(match.group(1))
    return 0


MAX_OUTPUT = 3000  # Truncate test output to prevent context blow-up


def run_tests(test_path: Optional[str] = None, framework: Optional[str] = None) -> str:
    """
    Run project tests.
    
    Args:
        test_path: Optional specific test file or directory to run.
        framework: Optional framework override ('pytest', 'npm', 'cargo', 'go').
    
    Returns:
        Formatted test result string for the LLM.
    """
    project_root = os.getcwd()

    # Detect or use override
    if framework:
        fw_map = {
            "pytest": {"name": "pytest", "base_cmd": ["python", "-m", "pytest"]},
            "npm": {"name": "npm", "base_cmd": ["npm", "test", "--"]},
            "cargo": {"name": "cargo", "base_cmd": ["cargo", "test"]},
            "go": {"name": "go", "base_cmd": ["go", "test", "./..."]},
        }
        fw = fw_map.get(framework)
        if not fw:
            return f"Error: Unknown test framework '{framework}'. Supported: pytest, npm, cargo, go."
    else:
        fw = _detect_framework(project_root)
        if not fw:
            return (
                "Error: No test framework detected. "
                "Looked for pytest, npm test, cargo test, go test. "
                "Ensure the project has a test configuration or tests/ directory."
            )

    # Build command
    cmd = list(fw["base_cmd"])

    if fw["name"] == "pytest":
        cmd.extend(["-v", "--tb=short", "--no-header"])
        if test_path:
            cmd.append(test_path)
    elif fw["name"] == "npm" and test_path:
        cmd.append(test_path)
    elif fw["name"] == "cargo" and test_path:
        cmd.extend(["--", test_path])
    elif fw["name"] == "go" and test_path:
        cmd = ["go", "test", "-v", test_path]

    # Run tests
    try:
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
        )

        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr
        output = output.strip()

        # Truncate if too long
        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT] + "\n\n... (output truncated)"

        success = result.returncode == 0

        # Parse failure count
        failed_count = 0
        if not success:
            if fw["name"] == "pytest":
                failed_count = _parse_pytest_failures(output)
            elif fw["name"] == "npm":
                failed_count = _parse_npm_failures(output)
            else:
                failed_count = 1  # Generic fallback

        # Format result
        status = "✅ PASSED" if success else f"❌ FAILED ({failed_count} failure(s))"
        return f"Test Result [{fw['name']}]: {status}\n\n{output}"

    except subprocess.TimeoutExpired:
        return f"Error: Tests timed out after 120 seconds (framework: {fw['name']})."
    except FileNotFoundError:
        return f"Error: Test command not found. Is '{fw['base_cmd'][0]}' installed?"
    except Exception as e:
        return f"Error running tests: {str(e)}"
