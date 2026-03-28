import os
import pytest
from src.tools.handlers import read_file, write_file, list_files

def test_file_operations(tmp_path):
    # Setup a temp file
    test_file = tmp_path / "test.txt"
    content = "Hello, Tool Handler!"
    
    # Test write_file
    result = write_file(str(test_file), content)
    assert "Successfully wrote to" in result
    assert os.path.exists(test_file)
    
    # Test read_file
    read_content = read_file(str(test_file))
    assert read_content == content
    
    # Test error cases
    assert "Error reading file" in read_file("non_existent_file.txt")

def test_list_files(tmp_path):
    (tmp_path / "file1.txt").touch()
    (tmp_path / "file2.txt").touch()
    
    result = list_files(str(tmp_path))
    assert "file1.txt" in result
    assert "file2.txt" in result
