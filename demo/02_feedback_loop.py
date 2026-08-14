"""Demo 2: Feedback loop — inject failure, agent receives feedback, changes behavior.

Uses MockLLM to deterministically demonstrate the feedback loop.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
from mecha.config import Config
from mecha.loop import run_loop
from tests.mock_llm import MockLLM


def main():
    print("=" * 60)
    print("Mecha Mechanism Demo 2: Feedback Loop")
    print("=" * 60)

    # Mock LLM: first writes buggy code, runs tests (fail), fixes, retests (pass)
    mock = MockLLM(responses=[
        # Step 1: Write buggy code
        '{"type": "write_file", "params": {"path": "test_demo.py", "content": "def test_math():\\n    assert 1 + 1 == 3  # BUG: should be 2"}, "reasoning": "write test file"}',
        # Step 2: Run tests — will fail
        '{"type": "run_command", "params": {"command": "pytest test_demo.py -v"}, "reasoning": "verify the test"}',
        # Step 3: After seeing failure, fix the code
        '{"type": "write_file", "params": {"path": "test_demo.py", "content": "def test_math():\\n    assert 1 + 1 == 2  # Fixed"}, "reasoning": "fix the assertion"}',
        # Step 4: Run tests again — will pass
        '{"type": "run_command", "params": {"command": "pytest test_demo.py -v"}, "reasoning": "verify the fix"}',
        # Step 5: Complete
        '{"type": "complete", "params": {"summary": "Fixed the test assertion"}, "reasoning": "task complete"}',
    ])

    config = Config()

    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_loop("write a test that passes", mock, config, tmpdir)

        print(f"\nResult: {'✅ SUCCESS' if result['success'] else '❌ FAILED'}")
        print(f"Iterations: {result['iterations']}")
        print(f"Summary: {result['summary']}")
        print(f"\nAudit trail:")
        for a in result["audit_actions"]:
            print(f"  [{a['iteration']}] {a['action']}: {a['command'][:60]} (guardrail: {a['guardrail']})")

        assert result["success"] is True
        assert result["iterations"] == 5

    print("\n" + "=" * 60)
    print("✅ Feedback loop demonstrated:")
    print("   1. Agent wrote buggy code (assert 1+1==3)")
    print("   2. Agent ran tests → tests failed")
    print("   3. Agent received feedback → understood the error")
    print("   4. Agent fixed the code (assert 1+1==2)")
    print("   5. Agent ran tests → tests passed")
    print("   6. Agent completed the task")
    print("=" * 60)


if __name__ == "__main__":
    main()