"""Memory module — cross-session memory storage and retrieval."""

import os
import json
from mecha.models import MemoryEntry


MEMORY_DIR = ".mecha/memory"


def _ensure_memory_dir() -> str:
    """Ensure the memory directory exists. Returns the path."""
    path = os.path.join(os.getcwd(), MEMORY_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def _get_total_size(memory_dir: str) -> int:
    """Get total size of all memory files in bytes."""
    total = 0
    for fname in os.listdir(memory_dir):
        fpath = os.path.join(memory_dir, fname)
        if os.path.isfile(fpath):
            total += os.path.getsize(fpath)
    return total


def save_memory(entry: MemoryEntry, max_total_size: int = 102_400) -> bool:
    """Save a memory entry to disk.

    Args:
        entry: The MemoryEntry to save.
        max_total_size: Maximum total size of all memory files in bytes.

    Returns:
        True if saved successfully, False if size limit exceeded.
    """
    memory_dir = _ensure_memory_dir()

    # Check total size before writing
    if _get_total_size(memory_dir) >= max_total_size:
        return False

    filepath = os.path.join(memory_dir, f"{entry.id}.json")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "id": entry.id,
                "session_id": entry.session_id,
                "task": entry.task,
                "summary": entry.summary,
                "decisions": entry.decisions,
                "created_at": entry.created_at,
            }, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def load_all_memories() -> list[MemoryEntry]:
    """Load all memory entries from disk.

    Returns:
        List of MemoryEntry objects (empty if directory doesn't exist or is empty).
    """
    memory_dir = os.path.join(os.getcwd(), MEMORY_DIR)
    if not os.path.exists(memory_dir):
        return []

    entries = []
    for fname in os.listdir(memory_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(memory_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            entries.append(MemoryEntry(
                id=data.get("id", ""),
                session_id=data.get("session_id", ""),
                task=data.get("task", ""),
                summary=data.get("summary", ""),
                decisions=data.get("decisions", []),
                created_at=data.get("created_at", ""),
            ))
        except (json.JSONDecodeError, KeyError):
            # Corrupted file — skip
            continue

    return entries


def search_memories(keyword: str) -> list[MemoryEntry]:
    """Search memories by keyword (case-insensitive).

    Args:
        keyword: Search keyword.

    Returns:
        Matching MemoryEntry list.
    """
    keyword_lower = keyword.lower()
    all_entries = load_all_memories()
    return [
        e for e in all_entries
        if keyword_lower in e.task.lower()
        or keyword_lower in e.summary.lower()
        or any(keyword_lower in d.lower() for d in e.decisions)
    ]


def format_memories_for_context(entries: list[MemoryEntry]) -> str:
    """Format memory entries as a string to inject into LLM context.

    Args:
        entries: List of MemoryEntry objects.

    Returns:
        Formatted string for LLM context.
    """
    if not entries:
        return ""

    lines = ["## Relevant Project Memory"]
    for entry in entries:
        lines.append(f"- [{entry.created_at[:10]}] Task: {entry.task}")
        lines.append(f"  Summary: {entry.summary}")
        if entry.decisions:
            lines.append(f"  Key decisions: {', '.join(entry.decisions)}")
    return "\n".join(lines)