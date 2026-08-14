"""Agent main loop — the core harness that orchestrates LLM + tools + guardrails + feedback."""

import json
import os
from mecha.models import Action, ActionResult, MemoryEntry
from mecha.config import Config
from mecha.llm.base import BaseLLM
from mecha.tools import read_file, write_file, run_command
from mecha.guardrails import guardrail, request_confirmation, log_audit
from mecha.feedback import get_feedback, is_test_command
from mecha.memory import save_memory, search_memories, format_memories_for_context


def _parse_action(text: str) -> Action | None:
    """Parse LLM response text into an Action. Returns None if parsing fails."""
    # Try to extract JSON from the response
    text = text.strip()
    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:]) if len(lines) > 1 else text
        if text.endswith("```"):
            text = text[: -3]

    try:
        data = json.loads(text)
        return Action(
            type=data["type"],
            params=data.get("params", {}),
            reasoning=data.get("reasoning", ""),
        )
    except (json.JSONDecodeError, KeyError):
        return None


def _build_context(task: str, project_root: str) -> str:
    """Build the initial context for the LLM."""
    context_parts = [f"Project root: {project_root}"]

    # List project files (top-level overview)
    try:
        files = []
        for root, dirs, fnames in os.walk(project_root):
            # Skip hidden dirs and venv
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for fname in fnames:
                if fname.startswith("."):
                    continue
                rel_path = os.path.relpath(os.path.join(root, fname), project_root)
                files.append(rel_path)
        context_parts.append(f"Project files:\n" + "\n".join(f"  - {f}" for f in files[:50]))
    except Exception:
        pass

    # Add relevant memory
    memories = search_memories(task)
    memory_text = format_memories_for_context(memories)
    if memory_text:
        context_parts.append(memory_text)

    return "\n\n".join(context_parts)


def run_loop(task: str, llm: BaseLLM, config: Config, project_root: str | None = None) -> dict:
    """Run the main agent loop.

    Args:
        task: The user's task description.
        llm: An LLM instance (real or mock).
        config: Mecha configuration.
        project_root: Project root directory. Defaults to current working directory.

    Returns:
        Dict with 'success', 'summary', 'iterations', 'audit_actions' keys.
    """
    if project_root is None:
        project_root = os.getcwd()

    # Build initial context
    context = _build_context(task, project_root)
    messages = _build_initial_messages(task, context, llm)

    iteration = 0
    test_round = 0
    audit_actions = []

    while iteration < config.max_iterations:
        iteration += 1

        # 1. Call LLM
        try:
            response = llm.chat(messages)
        except Exception as e:
            return {
                "success": False,
                "summary": f"LLM call failed: {e}",
                "iterations": iteration,
                "audit_actions": audit_actions,
            }

        # 2. Parse action
        action = _parse_action(response)
        if action is None:
            # Failed to parse — ask LLM to retry
            messages.append({"role": "assistant", "content": response})
            messages.append({
                "role": "user",
                "content": "Your response was not valid JSON. Please respond with ONLY a JSON object matching the required format.",
            })
            continue

        # 3. Check for completion
        if action.type == "complete":
            summary = action.params.get("summary", "Task completed.")
            # Save memory
            entry = MemoryEntry(
                task=task,
                summary=summary,
                decisions=[f"Completed in {iteration} iterations"],
            )
            save_memory(entry, config.memory_max_size)
            return {
                "success": True,
                "summary": summary,
                "iterations": iteration,
                "audit_actions": audit_actions,
            }

        # 4. Guardrail check
        decision = guardrail(
            action,
            custom_block=config.custom_danger_rules,
            custom_confirm=config.custom_confirm_rules,
        )
        audit_actions.append({
            "iteration": iteration,
            "action": action.type,
            "command": action.params.get("command", ""),
            "guardrail": decision.level,
            "reasoning": action.reasoning,
        })

        if decision.level == "block":
            log_audit(action, decision, executed=False)
            messages.append({"role": "assistant", "content": response})
            messages.append({
                "role": "user",
                "content": f"⚠️ Your action was BLOCKED by the safety guardrail: {decision.reason}\nPlease find an alternative approach.",
            })
            continue

        if decision.level == "confirm":
            confirmed = request_confirmation(action, decision)
            log_audit(action, decision, executed=confirmed)
            if not confirmed:
                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": "User denied this action. Please find an alternative approach.",
                })
                continue
        else:
            log_audit(action, decision, executed=True)

        # 5. Execute action
        result = _execute_action(action, project_root, config)

        # 6. Process feedback
        if action.type == "run_command":
            feedback = get_feedback(result, action.params.get("command", ""))
            # Check if this is a test command for tracking fix rounds
            if is_test_command(action.params.get("command", "")):
                if not result.success:
                    test_round += 1
                    if test_round > config.max_fix_rounds:
                        return {
                            "success": False,
                            "summary": f"Failed to fix tests after {config.max_fix_rounds} rounds.",
                            "iterations": iteration,
                            "audit_actions": audit_actions,
                        }
        else:
            feedback = result.output if result.success else f"Error: {result.error}"

        # 7. Feed back to LLM
        messages.append({"role": "assistant", "content": response})
        messages.append({
            "role": "user",
            "content": f"## Action Result\n{feedback}",
        })

    # Max iterations reached
    return {
        "success": False,
        "summary": f"Reached maximum iterations ({config.max_iterations}) without completing the task.",
        "iterations": iteration,
        "audit_actions": audit_actions,
    }


def _execute_action(action: Action, project_root: str, config: Config) -> ActionResult:
    """Execute an action based on its type."""
    if action.type == "read_file":
        return read_file(action.params.get("path", ""), project_root)

    if action.type == "write_file":
        return write_file(
            action.params.get("path", ""),
            action.params.get("content", ""),
            project_root,
            config.max_file_size,
        )

    if action.type == "run_command":
        return run_command(
            action.params.get("command", ""),
            project_root,
        )

    return ActionResult(success=False, error=f"Unknown action type: {action.type}")


def _build_initial_messages(task: str, context: str, llm: BaseLLM) -> list[dict]:
    """Build initial messages. Uses DeepSeekLLM.build_initial_messages if available."""
    if hasattr(llm, "build_initial_messages"):
        return llm.build_initial_messages(task, context)

    # Generic fallback
    user_message = f"## Task\n{task}\n\n## Context\n{context}"
    return [
        {"role": "system", "content": "You are a coding agent. Respond only with JSON actions."},
        {"role": "user", "content": user_message},
    ]