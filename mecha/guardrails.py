"""Guardrails module — three-layer safety system for command execution.

Layer 1: Static rule matching (pattern-based danger detection)
Layer 2: Tiered approval (allow / confirm / block)
Layer 3: Audit logging (structured JSON log)
"""

import re
import json
import os
from datetime import datetime, timezone
from mecha.models import Action, GuardrailDecision

# ── Layer 1: Default rule sets ──────────────────────────────────────────

DEFAULT_BLOCK_PATTERNS = [
    # Destructive filesystem operations
    r"rm\s+(-[rRf]+\s+)*/",             # rm -rf /
    r"rm\s+(-[rRf]+\s+)*\*",            # rm -rf *
    r"rm\s+(-[rRf]+\s+)*~",            # rm -rf ~
    # Privilege escalation
    r"\bsudo\b",
    r"\bsu\s",
    # Remote code execution
    r"curl\s+.*\|\s*(ba)?sh",           # curl | bash
    r"wget\s+.*\|\s*(ba)?sh",           # wget | bash
    r"curl\s+.*\|\s*(ba)?sh",           # curl | bash
    # Permission changes
    r"chmod\s+777",
    r"chmod\s+-R\s+777",
    r"chown\s+-R\s+",
    # Database destruction
    r"\bDROP\s+(TABLE|DATABASE)\b",
    r"\bTRUNCATE\s+(TABLE\s+)?\b",
    # System config modification
    r"write_file.*path.*['\"]/etc/",
    r">\s*/etc/",
    # Fork bomb
    r":\(\)\s*\{",
    # Dangerous io redirection
    r"dd\s+if=",
    r"mkfs\.",
]

DEFAULT_CONFIRM_PATTERNS = [
    # Package installation
    r"\bpip\s+install\b",
    r"\bpip3\s+install\b",
    r"\bnpm\s+install\b",
    r"\bnpm\s+i\b",
    r"\byarn\s+add\b",
    r"\bapt\s+install\b",
    r"\bbrew\s+install\b",
    # System config modification
    r"\bexport\s+\w+=",
    r"\bsource\s+",
    # Network operations
    r"\bcurl\b(?!.*\|.*sh)",
    r"\bwget\b(?!.*\|.*sh)",
    r"\bnc\s",
    # Git push to main/master
    r"git\s+push\b.*(main|master)",
    # Process management
    r"\bkill\b",
    r"\bkillall\b",
    r"\bpkill\b",
    # File deletion (non-system)
    r"\brm\s",
    r"\brmdir\b",
]

# ── Layer 2: Tiered approval ────────────────────────────────────────────

def _check_patterns(command: str, patterns: list[str]) -> str | None:
    """Check if command matches any pattern. Returns the first matching pattern."""
    for pattern in patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return pattern
    return None


def _classify_action(action: Action, custom_block: list[str] | None = None,
                     custom_confirm: list[str] | None = None) -> tuple[str, str]:
    """Classify an action into block/confirm/allow.

    Returns:
        (level, rule_matched) — level is 'block', 'confirm', or 'allow'
    """
    # Only guardrail shell commands
    if action.type != "run_command":
        return ("allow", "")

    command = action.params.get("command", "")

    # Check block patterns (default + custom)
    all_block = list(DEFAULT_BLOCK_PATTERNS) + (custom_block or [])
    matched = _check_patterns(command, all_block)
    if matched:
        return ("block", matched)

    # Check confirm patterns (default + custom)
    all_confirm = list(DEFAULT_CONFIRM_PATTERNS) + (custom_confirm or [])
    matched = _check_patterns(command, all_confirm)
    if matched:
        return ("confirm", matched)

    # Default: allow
    return ("allow", "")


def guardrail(action: Action, custom_block: list[str] | None = None,
              custom_confirm: list[str] | None = None) -> GuardrailDecision:
    """Run the guardrail check on an action.

    Args:
        action: The action to check.
        custom_block: Additional block patterns from user config.
        custom_confirm: Additional confirm patterns from user config.

    Returns:
        GuardrailDecision with level (allow/confirm/block) and metadata.
    """
    level, rule_matched = _classify_action(action, custom_block, custom_confirm)

    reasons = {
        "block": f"Blocked dangerous command matching rule: {rule_matched}",
        "confirm": f"Command requires confirmation (matched: {rule_matched})",
        "allow": "Command allowed by guardrail",
    }

    return GuardrailDecision(
        level=level,
        rule_matched=rule_matched,
        reason=reasons[level],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def request_confirmation(action: Action, decision: GuardrailDecision) -> bool:
    """Ask the user for y/n confirmation via terminal.

    Returns:
        True if user confirms, False otherwise.
    """
    command = action.params.get("command", "")
    print(f"\n⚠️  Guardrail: {decision.reason}")
    print(f"   Command: {command}")
    print(f"   LLM Reasoning: {action.reasoning}")
    response = input("   Execute? [y/N]: ").strip().lower()
    return response == "y"


# ── Layer 3: Audit logging ──────────────────────────────────────────────

def _get_audit_log_path() -> str:
    """Get the path to the audit log file."""
    log_dir = os.path.join(os.getcwd(), ".mecha", "logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "audit.jsonl")


def log_audit(action: Action, decision: GuardrailDecision, executed: bool) -> None:
    """Write an audit log entry.

    Args:
        action: The action that was checked.
        decision: The guardrail decision.
        executed: Whether the action was ultimately executed.
    """
    entry = {
        "timestamp": decision.timestamp,
        "action_type": action.type,
        "command": action.params.get("command", ""),
        "llm_reasoning": action.reasoning,
        "guardrail_level": decision.level,
        "rule_matched": decision.rule_matched,
        "executed": executed,
    }

    log_path = _get_audit_log_path()
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        # Audit log failure should not block execution
        pass