"""Integration tests for Agent Loop — uses MockLLM, no real LLM needed."""

import pytest
import os
import tempfile
from mecha.config import Config
from mecha.loop import run_loop
from tests.mock_llm import MockLLM


class TestLoopWithMockLLM:
    """Test the main loop with deterministic mock LLM responses."""

    def test_simple_complete_task(self):
        """Agent completes a task in one step."""
        mock = MockLLM(responses=[
            '{"type": "complete", "params": {"summary": "Done"}, "reasoning": "task is trivial"}',
        ])
        config = Config()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_loop("say hello", mock, config, tmpdir)
            assert result["success"] is True
            assert result["iterations"] == 1
            assert mock.call_count == 1

    def test_read_then_write_then_complete(self):
        """Agent reads a file, writes a file, then completes."""
        mock = MockLLM(responses=[
            '{"type": "read_file", "params": {"path": "input.txt"}, "reasoning": "need to read input"}',
            '{"type": "write_file", "params": {"path": "output.txt", "content": "processed"}, "reasoning": "write result"}',
            '{"type": "complete", "params": {"summary": "processed file"}, "reasoning": "done"}',
        ])
        config = Config()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create input file
            with open(os.path.join(tmpdir, "input.txt"), "w") as f:
                f.write("original")

            result = run_loop("process input.txt", mock, config, tmpdir)
            assert result["success"] is True
            assert result["iterations"] == 3
            assert mock.call_count == 3

    def test_guardrail_blocks_and_agent_retries(self):
        """Agent tries a dangerous command, gets blocked, then tries a safe alternative."""
        mock = MockLLM(responses=[
            '{"type": "run_command", "params": {"command": "sudo rm -rf /"}, "reasoning": "dangerous"}',
            '{"type": "run_command", "params": {"command": "ls -la"}, "reasoning": "safe alternative"}',
            '{"type": "complete", "params": {"summary": "used safe command"}, "reasoning": "done"}',
        ])
        config = Config()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_loop("list files", mock, config, tmpdir)
            assert result["success"] is True
            assert result["iterations"] == 3
            # Check audit log recorded the block
            assert any(a["guardrail"] == "block" for a in result["audit_actions"])

    def test_feedback_loop_after_test_failure(self):
        """Agent runs tests, they fail, agent fixes and retries."""
        mock = MockLLM(responses=[
            # First: write buggy code
            '{"type": "write_file", "params": {"path": "test_math.py", "content": "def test_add():\\n    assert 1+1 == 3"}, "reasoning": "write test"}',
            # Second: run tests (will fail)
            '{"type": "run_command", "params": {"command": "pytest test_math.py"}, "reasoning": "run tests"}',
            # Third: after seeing failure, fix
            '{"type": "write_file", "params": {"path": "test_math.py", "content": "def test_add():\\n    assert 1+1 == 2"}, "reasoning": "fix test"}',
            # Fourth: run tests again (will pass)
            '{"type": "run_command", "params": {"command": "pytest test_math.py"}, "reasoning": "verify fix"}',
            # Fifth: complete
            '{"type": "complete", "params": {"summary": "fixed test"}, "reasoning": "done"}',
        ])
        config = Config()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_loop("write and fix a test", mock, config, tmpdir)
            assert result["success"] is True
            assert result["iterations"] >= 3

    def test_max_iterations_reached(self):
        """Agent keeps going until max iterations is hit."""
        mock = MockLLM(responses=[
            '{"type": "read_file", "params": {"path": "x.txt"}, "reasoning": "reading"}',
        ] * 25)  # More than max
        config = Config(max_iterations=5)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_loop("read endlessly", mock, config, tmpdir)
            assert result["success"] is False
            assert "maximum" in result["summary"].lower()

    def test_invalid_json_retry(self):
        """Agent returns invalid JSON, gets asked to retry, then succeeds."""
        mock = MockLLM(responses=[
            "not valid json at all",
            '{"type": "complete", "params": {"summary": "done after retry"}, "reasoning": "retry worked"}',
        ])
        config = Config()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_loop("do something", mock, config, tmpdir)
            assert result["success"] is True
            assert mock.call_count == 2

    def test_audit_log_tracks_all_actions(self):
        """Audit log records every action attempt."""
        mock = MockLLM(responses=[
            '{"type": "run_command", "params": {"command": "ls"}, "reasoning": "list"}',
            '{"type": "run_command", "params": {"command": "rm -rf /"}, "reasoning": "bad"}',
            '{"type": "complete", "params": {"summary": "done"}, "reasoning": "done"}',
        ])
        config = Config()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_loop("mixed actions", mock, config, tmpdir)
            assert len(result["audit_actions"]) == 2  # Only run_command actions are audited
            assert result["audit_actions"][0]["guardrail"] == "allow"
            assert result["audit_actions"][1]["guardrail"] == "block"