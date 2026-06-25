import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def file_mcp(monkeypatch, tmp_path):
    monkeypatch.setenv("SANDBOX_DIR", str(tmp_path))
    module_path = Path(__file__).resolve().parents[1] / "mcp-server" / "server.py"
    spec = importlib.util.spec_from_file_location("test_file_mcp_server", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_safe_path_rejects_traversal(file_mcp):
    with pytest.raises(ValueError):
        file_mcp._safe_path("../outside.txt")


def test_write_read_list_search_and_delete_file(file_mcp):
    write_result = file_mcp.write_file("notes/a.txt", "hello").replace("\\", "/")
    assert write_result == "File written: notes/a.txt"

    assert file_mcp.read_file("notes/a.txt") == "hello"
    listing = file_mcp.list_directory("notes")
    assert "a.txt" in listing
    assert file_mcp.search_files("a.").replace("\\", "/") == "notes/a.txt"
    assert "Deleted:" in file_mcp.delete_file("notes/a.txt")
    assert file_mcp.read_file("notes/a.txt") == "File not found: notes/a.txt"


def test_delete_file_refuses_directories(file_mcp):
    file_mcp._safe_path("folder").mkdir()

    assert file_mcp.delete_file("folder") == "Cannot delete directories - use a file path only"


def test_read_missing_file_returns_clear_message(file_mcp):
    assert file_mcp.read_file("missing.txt") == "File not found: missing.txt"


def test_list_directory_rejects_file_path(file_mcp):
    file_mcp.write_file("a.txt", "hello")

    assert file_mcp.list_directory("a.txt") == "Not a directory: a.txt"


def test_tool_functions_return_security_errors_for_unsafe_paths(file_mcp):
    assert file_mcp.read_file("../x").startswith("Security error:")
    assert file_mcp.write_file("../x", "bad").startswith("Security error:")
    assert file_mcp.delete_file("../x").startswith("Security error:")

