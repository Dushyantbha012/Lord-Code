"""Tests for the tool system — registry and individual tools."""

import os
import pytest
from pathlib import Path

from src.tools.base import ToolResult, RiskLevel
from src.tools.registry import ToolRegistry
from src.tools.read_file import ReadFileTool
from src.tools.write_file import WriteFileTool
from src.tools.list_directory import ListDirectoryTool
from src.tools.run_command import RunCommandTool


class TestToolRegistry:
    """Test tool registration and dispatch."""

    def test_register_and_get(self, tmp_path):
        registry = ToolRegistry()
        tool = ReadFileTool(str(tmp_path))
        registry.register(tool)
        assert registry.get("read_file") is tool

    def test_get_missing_tool(self):
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_execute_missing_tool(self):
        registry = ToolRegistry()
        result = await registry.execute("nonexistent", {})
        assert not result.success
        assert "Unknown tool" in result.output

    def test_get_schemas(self, tmp_path):
        registry = ToolRegistry()
        registry.register(ReadFileTool(str(tmp_path)))
        schemas = registry.get_schemas()
        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "read_file"

    def test_get_tool_names(self, tmp_path):
        registry = ToolRegistry()
        registry.register(ReadFileTool(str(tmp_path)))
        registry.register(ListDirectoryTool(str(tmp_path)))
        names = registry.get_tool_names()
        assert "read_file" in names
        assert "list_directory" in names


class TestReadFileTool:
    """Test the read_file tool."""

    @pytest.mark.asyncio
    async def test_read_existing_file(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')\n")

        tool = ReadFileTool(str(tmp_path))
        result = await tool.execute(file_path="test.py")
        assert result.success
        assert "print('hello')" in result.output
        assert "1 |" in result.output  # Line numbers

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, tmp_path):
        tool = ReadFileTool(str(tmp_path))
        result = await tool.execute(file_path="nonexistent.py")
        assert not result.success
        assert "not found" in result.output.lower()

    @pytest.mark.asyncio
    async def test_read_binary_file(self, tmp_path):
        test_file = tmp_path / "image.png"
        test_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        tool = ReadFileTool(str(tmp_path))
        result = await tool.execute(file_path="image.png")
        assert result.success
        assert "Binary" in result.output

    @pytest.mark.asyncio
    async def test_read_path_traversal_blocked(self, tmp_path):
        tool = ReadFileTool(str(tmp_path))
        result = await tool.execute(file_path="../../etc/passwd")
        assert not result.success
        assert "denied" in result.output.lower() or "outside" in result.output.lower()

    def test_risk_level(self, tmp_path):
        tool = ReadFileTool(str(tmp_path))
        assert tool.risk_level == RiskLevel.SAFE


class TestWriteFileTool:
    """Test the write_file tool."""

    @pytest.mark.asyncio
    async def test_create_new_file(self, tmp_path):
        tool = WriteFileTool(str(tmp_path))
        result = await tool.execute(
            file_path="new_file.py",
            content="print('hello world')\n",
        )
        assert result.success
        assert (tmp_path / "new_file.py").exists()
        assert (tmp_path / "new_file.py").read_text() == "print('hello world')\n"

    @pytest.mark.asyncio
    async def test_create_nested_file(self, tmp_path):
        tool = WriteFileTool(str(tmp_path))
        result = await tool.execute(
            file_path="src/utils/helper.py",
            content="# helper\n",
        )
        assert result.success
        assert (tmp_path / "src" / "utils" / "helper.py").exists()

    @pytest.mark.asyncio
    async def test_overwrite_existing_file(self, tmp_path):
        existing = tmp_path / "existing.py"
        existing.write_text("old content\n")

        tool = WriteFileTool(str(tmp_path))
        result = await tool.execute(
            file_path="existing.py",
            content="new content\n",
        )
        assert result.success
        assert existing.read_text() == "new content\n"
        assert "diff" in result.metadata or "Modified" in result.output

    @pytest.mark.asyncio
    async def test_write_path_traversal_blocked(self, tmp_path):
        tool = WriteFileTool(str(tmp_path))
        result = await tool.execute(
            file_path="../../evil.py",
            content="import os; os.system('echo hacked')\n",
        )
        assert not result.success

    def test_risk_level(self, tmp_path):
        tool = WriteFileTool(str(tmp_path))
        assert tool.risk_level == RiskLevel.MODERATE


class TestListDirectoryTool:
    """Test the list_directory tool."""

    @pytest.mark.asyncio
    async def test_list_project_root(self, tmp_path):
        (tmp_path / "file1.py").write_text("print(1)")
        (tmp_path / "file2.js").write_text("console.log(1)")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "nested.txt").write_text("hello")

        tool = ListDirectoryTool(str(tmp_path))
        result = await tool.execute(path=".")
        assert result.success
        assert "file1.py" in result.output
        assert "file2.js" in result.output
        assert "subdir" in result.output

    @pytest.mark.asyncio
    async def test_list_nonexistent_dir(self, tmp_path):
        tool = ListDirectoryTool(str(tmp_path))
        result = await tool.execute(path="nonexistent")
        assert not result.success

    @pytest.mark.asyncio
    async def test_recursive_listing(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print(1)")
        (tmp_path / "src" / "utils").mkdir()
        (tmp_path / "src" / "utils" / "helper.py").write_text("print(2)")

        tool = ListDirectoryTool(str(tmp_path))
        result = await tool.execute(path=".", recursive=True)
        assert result.success
        assert "main.py" in result.output
        assert "helper.py" in result.output

    def test_risk_level(self, tmp_path):
        tool = ListDirectoryTool(str(tmp_path))
        assert tool.risk_level == RiskLevel.SAFE


class TestRunCommandTool:
    """Test the run_command tool."""

    @pytest.mark.asyncio
    async def test_simple_command(self, tmp_path):
        tool = RunCommandTool(str(tmp_path), timeout=10)
        result = await tool.execute(command="echo 'hello world'")
        assert result.success
        assert "hello world" in result.output

    @pytest.mark.asyncio
    async def test_command_failure(self, tmp_path):
        tool = RunCommandTool(str(tmp_path), timeout=10)
        result = await tool.execute(command="ls /nonexistent_path_xyz")
        assert not result.success
        assert result.metadata["exit_code"] != 0

    @pytest.mark.asyncio
    async def test_command_timeout(self, tmp_path):
        tool = RunCommandTool(str(tmp_path), timeout=1)
        result = await tool.execute(command="sleep 10")
        assert not result.success
        assert "timed out" in result.output.lower()

    def test_risk_level(self, tmp_path):
        tool = RunCommandTool(str(tmp_path))
        assert tool.risk_level == RiskLevel.DANGEROUS
