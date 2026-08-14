"""Unit tests for Feedback module — deterministic, no real LLM needed."""

import pytest
from mecha.models import ActionResult
from mecha.feedback import (
    is_test_command,
    parse_test_output,
    format_feedback,
    get_feedback,
    _extract_pytest_failures,
)


class TestIsTestCommand:
    def test_pytest_detected(self):
        assert is_test_command("pytest") is True
        assert is_test_command("python -m pytest tests/") is True
        assert is_test_command("pytest -v test_foo.py") is True

    def test_non_test_commands(self):
        assert is_test_command("ls -la") is False
        assert is_test_command("python main.py") is False
        assert is_test_command("pip install requests") is False


class TestParsePytestOutput:
    def test_parse_pass(self):
        result = ActionResult(success=True, output="3 passed in 0.5s", exit_code=0)
        parsed = parse_test_output(result)
        assert parsed["status"] == "pass"
        assert "All tests passed" in parsed["summary"]

    def test_parse_fail(self):
        output = """
============================= FAILURES =============================
FAILED test_foo.py::test_add - AssertionError: assert 3 == 5
============================= short test summary ==========================
FAILED test_foo.py::test_add
1 passed, 1 failed in 0.5s
"""
        result = ActionResult(success=False, output=output, error="", exit_code=1)
        parsed = parse_test_output(result)
        assert parsed["status"] == "fail"
        assert len(parsed["failures"]) >= 1

    def test_parse_pass_with_zero_exit_code(self):
        result = ActionResult(success=True, output="OK", exit_code=0)
        parsed = parse_test_output(result)
        assert parsed["status"] == "pass"


class TestExtractFailures:
    def test_extract_from_failure_output(self):
        output = """
FAILED tests/test_foo.py::test_add - AssertionError: assert 3 == 5
FAILED tests/test_foo.py::test_sub - AssertionError: assert -1 == 1
"""
        failures = _extract_pytest_failures(output)
        assert len(failures) >= 1


class TestFormatFeedback:
    def test_format_pass(self):
        parsed = {"status": "pass", "failures": [], "summary": "All tests passed.", "raw_output": ""}
        feedback = format_feedback(parsed)
        assert "passed" in feedback.lower() or "complete" in feedback.lower()

    def test_format_fail(self):
        parsed = {
            "status": "fail",
            "failures": [{"test": "test_foo.py::test_add", "error": "assert 3 == 5"}],
            "summary": "1 test(s) failed.",
            "raw_output": "FAILED test_foo.py::test_add",
        }
        feedback = format_feedback(parsed)
        assert "fail" in feedback.lower() or "failed" in feedback.lower()
        assert "test_add" in feedback

    def test_format_unknown(self):
        parsed = {"status": "unknown", "failures": [], "summary": "blah", "raw_output": "hello"}
        feedback = format_feedback(parsed)
        assert "hello" in feedback


class TestGetFeedback:
    def test_get_feedback_test_pass(self):
        result = ActionResult(success=True, output="3 passed", exit_code=0)
        feedback = get_feedback(result, "pytest")
        assert "pass" in feedback.lower() or "complete" in feedback.lower()

    def test_get_feedback_test_fail(self):
        result = ActionResult(success=False, output="1 failed", error="", exit_code=1)
        feedback = get_feedback(result, "pytest")
        assert "fail" in feedback.lower() or "failed" in feedback.lower()

    def test_get_feedback_non_test(self):
        result = ActionResult(success=True, output="Hello World", exit_code=0)
        feedback = get_feedback(result, "python hello.py")
        assert "Hello World" in feedback

    def test_get_feedback_non_test_error(self):
        result = ActionResult(success=False, error="command not found", exit_code=127)
        feedback = get_feedback(result, "bad-command")
        assert "fail" in feedback.lower() or "command not found" in feedback