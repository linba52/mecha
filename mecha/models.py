"""Data models for Mecha harness."""

from dataclasses import dataclass, field
from typing import Literal
import uuid
from datetime import datetime, timezone


@dataclass
class Action:
    """An action the LLM wants to execute."""
    type: Literal["read_file", "write_file", "run_command", "complete"]
    params: dict  # {path?, content?, command?, summary?}
    reasoning: str = ""


@dataclass
class ActionResult:
    """Result of executing an action."""
    success: bool
    output: str = ""
    error: str = ""
    exit_code: int = 0


@dataclass
class GuardrailDecision:
    """Result of guardrail check on an action."""
    level: Literal["allow", "confirm", "block"]
    rule_matched: str = ""
    reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class MemoryEntry:
    """A memory entry stored across sessions."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task: str = ""
    summary: str = ""
    decisions: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())