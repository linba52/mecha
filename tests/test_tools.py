"""Unit tests for Tools module."""

import pytest
import os
import tempfile
from mecha.tools import read_file, write_file, run_command, _is_safe_path


class TestIsSafePath:
    def test_valid_path(self):
        assert _is_safe_path("src/main.py", "/home/user/project") is True

    def test_traversal_blocked(self):
        assert _is_safe_path("../../../etc/passwd", "/home/user/project") is False

    def test_traversal_dotdot(self):
        assert _is_safe_path("../other/file.txt", "/home/user/project") is False

    def test_root_path(self):
        assert _is_safe_path(".", "/home/user/project") is True


class TestReadFile:
    def test_read_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.txt")
            with open(filepath, "w") as f:
                f.write("hello world")

            result = read_file("test.txt", tmpdir)
            assert result.success is True
            assert result.output == "hello world"

    def test_read_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = read_file("nonexistent.txt", tmpdir)
            assert result.success is False
            assert "not found" in result.error.lower()

    def test_read_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = read_file("../../etc/passwd", tmpdir)
            assert result.success is False
            assert "traversal" in result.error.lower() or "security" in result.error.lower()


class TestWriteFile:
    def test_write_and_read(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = write_file("output.txt", "hello", tmpdir)
            assert result.success is True

            with open(os.path.join(tmpdir, "output.txt"), "r") as f:
                assert f.read() == "hello"

    def test_write_nested_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = write_file("sub/dir/file.txt", "content", tmpdir)
            assert result.success is True
            assert os.path.exists(os.path.join(tmpdir, "sub/dir/file.txt"))

    def test_write_size_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            huge_content = "x" * 2_000_000  # 2MB
            result = write_file("big.txt", huge_content, tmpdir, max_size=1_048_576)
            assert result.success is False
            assert "size" in result.error.lower()

    def test_write_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = write_file("../../etc/hack.txt", "evil", tmpdir)
            assert result.success is False


class TestRunCommand:
    def test_run_simple_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_command("echo hello", tmpdir)
            assert result.success is True
            assert result.output == "hello"

    def test_run_failing_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_command("python -c 'exit(1)'", tmpdir)
            assert result.success is False
            assert result.exit_code == 1

    def test_run_command_in_working_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_command("pwd", tmpdir)
            assert result.success is True