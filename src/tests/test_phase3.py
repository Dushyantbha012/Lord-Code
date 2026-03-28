"""
Tests for Phase 3 features:
- 3.1: Diff-based editing (edit_file)
- 3.4: Git tools
- 3.5: Undo/rollback system
- 3.2: Linter detection
- 3.3: Test runner detection
"""

import os
import tempfile
import pytest

# ── 3.5: Undo System Tests ──

from src.tools.undo import UndoManager


class TestUndoManager:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = UndoManager(self.tmpdir)

    def test_checkpoint_and_undo_restores_content(self):
        """Checkpoint + undo should restore original file content."""
        filepath = os.path.join(self.tmpdir, "test.txt")
        with open(filepath, "w") as f:
            f.write("original content")

        self.manager.begin_turn("test edit")
        self.manager.checkpoint(filepath)

        # Simulate a write
        with open(filepath, "w") as f:
            f.write("modified content")
        self.manager.record_write(filepath)
        self.manager.end_turn()

        # Verify modified
        with open(filepath, "r") as f:
            assert f.read() == "modified content"

        # Undo
        result = self.manager.undo_last()
        assert "Restored" in result

        # Verify restored
        with open(filepath, "r") as f:
            assert f.read() == "original content"

    def test_undo_new_file_deletes_it(self):
        """Undo on a newly created file should delete it."""
        filepath = os.path.join(self.tmpdir, "new_file.txt")

        self.manager.begin_turn("create file")
        self.manager.checkpoint(filepath)  # File doesn't exist yet

        with open(filepath, "w") as f:
            f.write("new content")
        self.manager.record_write(filepath)
        self.manager.end_turn()

        assert os.path.exists(filepath)

        result = self.manager.undo_last()
        assert "Deleted" in result
        assert not os.path.exists(filepath)

    def test_empty_undo(self):
        """Undo with no changes should return informative message."""
        result = self.manager.undo_last()
        assert "Nothing to undo" in result

    def test_change_log(self):
        """Change log should show recorded changes."""
        filepath = os.path.join(self.tmpdir, "log_test.txt")
        with open(filepath, "w") as f:
            f.write("v1")

        self.manager.begin_turn("first edit")
        self.manager.checkpoint(filepath)
        with open(filepath, "w") as f:
            f.write("v2")
        self.manager.record_write(filepath)
        self.manager.end_turn()

        log = self.manager.get_change_log()
        assert "1 change set" in log
        assert "first edit" in log

    def test_multiple_undos(self):
        """Multiple undo operations should work in reverse order."""
        file1 = os.path.join(self.tmpdir, "a.txt")
        file2 = os.path.join(self.tmpdir, "b.txt")

        with open(file1, "w") as f:
            f.write("a-original")

        # Turn 1
        self.manager.begin_turn("edit a")
        self.manager.checkpoint(file1)
        with open(file1, "w") as f:
            f.write("a-modified")
        self.manager.record_write(file1)
        self.manager.end_turn()

        # Turn 2
        self.manager.begin_turn("create b")
        self.manager.checkpoint(file2)
        with open(file2, "w") as f:
            f.write("b-content")
        self.manager.record_write(file2)
        self.manager.end_turn()

        # Undo turn 2 first
        self.manager.undo_last()
        assert not os.path.exists(file2)
        with open(file1, "r") as f:
            assert f.read() == "a-modified"

        # Undo turn 1
        self.manager.undo_last()
        with open(file1, "r") as f:
            assert f.read() == "a-original"


# ── 3.1: Edit File Tests ──

from src.tools.edit_file import edit_file, generate_diff


class TestEditFile:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_search_replace_basic(self):
        """Basic search/replace should work."""
        filepath = os.path.join(self.tmpdir, "hello.py")
        with open(filepath, "w") as f:
            f.write('print("hello")\nprint("world")\n')

        result = edit_file(filepath, [
            {"search": '"hello"', "replace": '"hi"'}
        ])
        assert "Successfully applied 1 edit" in result
        with open(filepath, "r") as f:
            content = f.read()
        assert '"hi"' in content
        assert '"world"' in content

    def test_search_not_found(self):
        """Missing search text should return error."""
        filepath = os.path.join(self.tmpdir, "test.py")
        with open(filepath, "w") as f:
            f.write("x = 1\n")

        result = edit_file(filepath, [
            {"search": "does_not_exist", "replace": "replacement"}
        ])
        assert "Error" in result
        assert "No edits were applied" in result

    def test_file_not_found(self):
        """Non-existent file should return error."""
        result = edit_file("/nonexistent/file.py", [
            {"search": "a", "replace": "b"}
        ])
        assert "Error" in result
        assert "does not exist" in result

    def test_multiple_edits(self):
        """Multiple edits in one call should all apply."""
        filepath = os.path.join(self.tmpdir, "multi.py")
        with open(filepath, "w") as f:
            f.write("x = 1\ny = 2\nz = 3\n")

        result = edit_file(filepath, [
            {"search": "x = 1", "replace": "x = 10"},
            {"search": "z = 3", "replace": "z = 30"},
        ])
        assert "Successfully applied 2 edit" in result
        with open(filepath, "r") as f:
            content = f.read()
        assert "x = 10" in content
        assert "y = 2" in content
        assert "z = 30" in content

    def test_generate_diff(self):
        """Diff generation should produce valid unified diff."""
        diff = generate_diff("hello\nworld\n", "hello\nearth\n", "test.txt")
        assert "-world" in diff
        assert "+earth" in diff

    def test_edit_with_undo_integration(self):
        """Edit should work with undo manager."""
        filepath = os.path.join(self.tmpdir, "undo_test.py")
        with open(filepath, "w") as f:
            f.write("original = True\n")

        manager = UndoManager(self.tmpdir)
        manager.begin_turn("test")

        result = edit_file(filepath, [
            {"search": "original = True", "replace": "original = False"}
        ], undo_manager=manager)

        manager.end_turn()
        assert "Successfully applied" in result

        # Undo
        manager.undo_last()
        with open(filepath, "r") as f:
            assert f.read() == "original = True\n"


# ── 3.4: Git Tools Tests ──

from src.tools.git_tools import git_status, _run_git


class TestGitTools:
    def test_git_status_runs(self):
        """git_status should return something (we're in a git repo)."""
        result = git_status()
        # Should not be an error (we are in a git repo)
        assert "Error: git is not installed" not in result

    def test_run_git_with_invalid_command(self):
        """Invalid git subcommand should return error."""
        result = _run_git("definitely-not-a-real-subcommand")
        assert "Error" in result


# ── 3.2: Linter Detection Tests ──

from src.tools.linter import detect_linter


class TestLinterDetection:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_detect_ruff_from_pyproject(self):
        """Should detect ruff when pyproject.toml has [tool.ruff]."""
        pyproject = os.path.join(self.tmpdir, "pyproject.toml")
        with open(pyproject, "w") as f:
            f.write("[tool.ruff]\nselect = ['E', 'F']\n")

        result = detect_linter("test.py", self.tmpdir)
        assert result is not None
        assert result["name"] == "ruff"

    def test_detect_eslint(self):
        """Should detect eslint when .eslintrc.json exists."""
        eslintrc = os.path.join(self.tmpdir, ".eslintrc.json")
        with open(eslintrc, "w") as f:
            f.write("{}")

        result = detect_linter("app.js", self.tmpdir)
        assert result is not None
        assert result["name"] == "eslint"

    def test_no_linter_for_unknown_ext(self):
        """Should return None for file types with no linter config."""
        result = detect_linter("data.csv", self.tmpdir)
        assert result is None


# ── 3.3: Test Runner Detection Tests ──

from src.tools.test_runner import _detect_framework


class TestTestRunnerDetection:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_detect_pytest_from_conftest(self):
        """Should detect pytest when conftest.py exists."""
        conftest = os.path.join(self.tmpdir, "conftest.py")
        with open(conftest, "w") as f:
            f.write("")

        result = _detect_framework(self.tmpdir)
        assert result is not None
        assert result["name"] == "pytest"

    def test_detect_npm_from_package_json(self):
        """Should detect npm test when package.json has test script."""
        import json
        pkg = os.path.join(self.tmpdir, "package.json")
        with open(pkg, "w") as f:
            json.dump({"scripts": {"test": "jest"}}, f)

        result = _detect_framework(self.tmpdir)
        assert result is not None
        assert result["name"] == "npm"

    def test_detect_cargo(self):
        """Should detect cargo test when Cargo.toml exists."""
        cargo = os.path.join(self.tmpdir, "Cargo.toml")
        with open(cargo, "w") as f:
            f.write("[package]\nname = 'test'\n")

        result = _detect_framework(self.tmpdir)
        assert result is not None
        assert result["name"] == "cargo"

    def test_no_framework_detected(self):
        """Should return None when no test framework indicators exist."""
        result = _detect_framework(self.tmpdir)
        assert result is None

    def test_detect_pytest_from_tests_dir(self):
        """Should detect pytest from tests/ directory with test_*.py files."""
        tests_dir = os.path.join(self.tmpdir, "tests")
        os.makedirs(tests_dir)
        with open(os.path.join(tests_dir, "test_something.py"), "w") as f:
            f.write("")

        result = _detect_framework(self.tmpdir)
        assert result is not None
        assert result["name"] == "pytest"
