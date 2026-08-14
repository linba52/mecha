"""Feedback module — parses test output and formats feedback for LLM."""

import re
from mecha.models import ActionResult


def is_test_command(command: str) -> bool:
    """Check if a command is a test execution command."""
    test_indicators = ["pytest", "python -m pytest", "python -m unittest", "tox"]
    return any(indicator in command for indicator in test_indicators)


def parse_test_output(result: ActionResult) -> dict:
    """Parse pytest output to extract structured failure information.

    Args:
        result: ActionResult from running a test command.

    Returns:
        Dict with keys: 'status' (pass/fail/error), 'failures' (list of failure dicts),
        'summary' (str), 'raw_output' (str).
    """
    output = f"{result.output}\n{result.error}".strip()

    if not is_test_command("pytest"):
        return {
            "status": "unknown",
            "failures": [],
            "summary": "Not a pytest command — output cannot be parsed structurally.",
            "raw_output": output,
        }

    if result.exit_code == 0:
        return {
            "status": "pass",
            "failures": [],
            "summary": "All tests passed.",
            "raw_output": output,
        }

    # Parse pytest failure output
    failures = _extract_pytest_failures(output)

    return {
        "status": "fail",
        "failures": failures,
        "summary": f"{len(failures)} test(s) failed.",
        "raw_output": output,
    }


def _extract_pytest_failures(output: str) -> list[dict]:
    """Extract individual failure details from pytest output."""
    failures = []
    # Match: FAILED test_file.py::test_name - AssertionError: message
    # Also match: > actual line
    pattern = r"FAILED\s+([^\s]+).*?\n(?:.*?\n)*?.*?(?:AssertionError|Error|Exception):\s*(.*?)(?:\n|$)"
    matches = re.findall(pattern, output, re.MULTILINE)

    for match in matches:
        failures.append({
            "test": match[0].strip(),
            "error": match[1].strip() if len(match) > 1 else "Unknown error",
        })

    # Fallback: if regex didn't match, try simpler pattern
    if not failures:
        simple_pattern = r"FAILED\s+([^\s]+)"
        for m in re.findall(simple_pattern, output):
            failures.append({
                "test": m.strip(),
                "error": "See raw output for details",
            })

    return failures


def format_feedback(parsed: dict) -> str:
    """Format parsed test output into a feedback message for the LLM.

    Args:
        parsed: Dict from parse_test_output().

    Returns:
        A formatted feedback string to inject into the LLM context.
    """
    if parsed["status"] == "pass":
        return "✅ All tests passed. The task is complete."

    if parsed["status"] == "fail":
        lines = ["❌ Tests failed. Please fix the following errors:"]
        for i, failure in enumerate(parsed["failures"], 1):
            lines.append(f"  {i}. {failure['test']}")
            lines.append(f"     Error: {failure['error']}")
        lines.append(f"\nRaw test output:\n{parsed['raw_output']}")
        return "\n".join(lines)

    # Unknown status — just pass through raw output
    return f"Command output:\n{parsed['raw_output']}"


def get_feedback(result: ActionResult, command: str) -> str:
    """Main entry point: given a command result, return formatted feedback for LLM.

    Args:
        result: ActionResult from command execution.
        command: The command that was executed.

    Returns:
        Formatted feedback string.
    """
    if not is_test_command(command):
        # Non-test commands: return raw output
        if result.success:
            return result.output
        else:
            return f"Command failed (exit code {result.exit_code}):\n{result.error or result.output}"

    parsed = parse_test_output(result)
    return format_feedback(parsed)