"""Agent main loop — the core harness that orchestrates LLM + tools + guardrails + feedback."""

import json
import os
import re
from mecha.models import Action, ActionResult, MemoryEntry
from mecha.config import Config
from mecha.llm.base import BaseLLM
from mecha.tools import read_file, write_file, run_command
from mecha.guardrails import guardrail, request_confirmation, log_audit
from mecha.feedback import get_feedback, is_test_command
from mecha.memory import save_memory, search_memories, format_memories_for_context


def _extract_json(text):
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*\n', '', text)
    text = re.sub(r'\n```\s*$', '', text)
    start = text.find('{')
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[start:i+1]
    return None


def _parse_action(text):
    json_str = _extract_json(text)
    if json_str is None:
        return None
    try:
        data = json.loads(json_str)
        if "type" not in data:
            return None
        return Action(type=data["type"], params=data.get("params", {}), reasoning=data.get("reasoning", ""))
    except (json.JSONDecodeError, KeyError):
        return None


def _build_context(task, project_root):
    context_parts = [f"Project root: {project_root}"]
    try:
        files = []
        for root, dirs, fnames in os.walk(project_root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for fname in fnames:
                if fname.startswith("."):
                    continue
                rel_path = os.path.relpath(os.path.join(root, fname), project_root)
                files.append(rel_path)
        context_parts.append(f"Project files:\n" + "\n".join(f"  - {f}" for f in files[:50]))
    except Exception:
        pass
    memories = search_memories(task)
    memory_text = format_memories_for_context(memories)
    if memory_text:
        context_parts.append(memory_text)
    return "\n\n".join(context_parts)


def run_loop(task, llm, config, project_root=None):
    if project_root is None:
        project_root = os.getcwd()
    context = _build_context(task, project_root)
    messages = _build_initial_messages(task, context, llm)
    iteration = 0
    test_round = 0
    audit_actions = []
    while iteration < config.max_iterations:
        iteration += 1
        try:
            response = llm.chat(messages)
        except Exception as e:
            return {"success": False, "summary": f"LLM call failed: {e}", "iterations": iteration, "audit_actions": audit_actions}
        action = _parse_action(response)
        if action is None:
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": "Your response was not valid JSON. Please respond with ONLY a JSON object."})
            continue
        if action.type == "complete":
            summary = action.params.get("summary", "Task completed.")
            entry = MemoryEntry(task=task, summary=summary, decisions=[f"Completed in {iteration} iterations"])
            save_memory(entry, config.memory_max_size)
            return {"success": True, "summary": summary, "iterations": iteration, "audit_actions": audit_actions}
        decision = guardrail(action, custom_block=config.custom_danger_rules, custom_confirm=config.custom_confirm_rules)
        audit_actions.append({"iteration": iteration, "action": action.type, "command": action.params.get("command", ""), "guardrail": decision.level, "reasoning": action.reasoning})
        if decision.level == "block":
            log_audit(action, decision, executed=False)
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"Your action was BLOCKED: {decision.reason}"})
            continue
        if decision.level == "confirm":
            confirmed = request_confirmation(action, decision)
            log_audit(action, decision, executed=confirmed)
            if not confirmed:
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": "User denied. Try another approach."})
                continue
        else:
            log_audit(action, decision, executed=True)
        result = _execute_action(action, project_root, config)
        if action.type == "run_command":
            feedback = get_feedback(result, action.params.get("command", ""))
            if is_test_command(action.params.get("command", "")):
                if not result.success:
                    test_round += 1
                    if test_round > config.max_fix_rounds:
                        return {"success": False, "summary": f"Failed to fix tests after {config.max_fix_rounds} rounds.", "iterations": iteration, "audit_actions": audit_actions}
        else:
            feedback = result.output if result.success else f"Error: {result.error}"
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": f"## Action Result\n{feedback}"})
    return {"success": False, "summary": f"Reached max iterations ({config.max_iterations}).", "iterations": iteration, "audit_actions": audit_actions}


def _print_conv_usage(llm):
    if hasattr(llm, "last_usage"):
        u = llm.last_usage
        t = llm.total_tokens
        print(f"[Tokens: {u['total_tokens']} | Total: {t} (P:{llm.total_prompt_tokens} C:{llm.total_completion_tokens})]")


def run_conversation(llm, config, project_root=None):
    if project_root is None:
        project_root = os.getcwd()
    sys_msg = llm.build_initial_messages("", "")[0] if hasattr(llm, "build_initial_messages") else {"role": "system", "content": "You are a helpful coding agent."}
    messages = [sys_msg]
    print("Mecha REPL — type a task or 'exit' to quit\n")
    while True:
        try:
            user_input = input("mecha> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye.")
            break
        messages.append({"role": "user", "content": user_input})
        iteration = 0
        while iteration < config.max_iterations:
            iteration += 1
            try:
                response = llm.chat(messages)
            except Exception as e:
                print(f"Error: {e}")
                break
            action = _parse_action(response)
            if action is None:
                print(f"\n{response}\n")
                _print_conv_usage(llm)
                messages.append({"role": "assistant", "content": response})
                break
            if action.type == "complete":
                summary = action.params.get("summary", "Done.")
                print(f"\n{summary}\n")
                _print_conv_usage(llm)
                messages.append({"role": "assistant", "content": response})
                break
            decision = guardrail(action, custom_block=config.custom_danger_rules, custom_confirm=config.custom_confirm_rules)
            if decision.level == "block":
                log_audit(action, decision, executed=False)
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": f"Action blocked: {decision.reason}"})
                continue
            if decision.level == "confirm":
                confirmed = request_confirmation(action, decision)
                log_audit(action, decision, executed=confirmed)
                if not confirmed:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": "User denied."})
                    continue
            else:
                log_audit(action, decision, executed=True)
            result = _execute_action(action, project_root, config)
            if action.type == "run_command":
                feedback = get_feedback(result, action.params.get("command", ""))
            else:
                feedback = result.output if result.success else f"Error: {result.error}"
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": f"Action result: {feedback}"})


def _execute_action(action, project_root, config):
    if action.type == "read_file":
        return read_file(action.params.get("path", ""), project_root)
    if action.type == "write_file":
        return write_file(action.params.get("path", ""), action.params.get("content", ""), project_root, config.max_file_size)
    if action.type == "run_command":
        return run_command(action.params.get("command", ""), project_root)
    return ActionResult(success=False, error=f"Unknown action type: {action.type}")


def _build_initial_messages(task, context, llm):
    if hasattr(llm, "build_initial_messages"):
        return llm.build_initial_messages(task, context)
    return [{"role": "system", "content": "You are a coding agent."}, {"role": "user", "content": f"## Task\n{task}\n\n## Context\n{context}"}]
