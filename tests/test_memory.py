"""Unit tests for Memory module."""

import pytest
import tempfile
import os
import shutil
import uuid
from mecha.models import MemoryEntry
from mecha.memory import (
    save_memory,
    load_all_memories,
    search_memories,
    format_memories_for_context,
)


class TestMemorySaveLoad:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                entry = MemoryEntry(
                    task="test task",
                    summary="did something",
                    decisions=["chose option A"],
                )
                success = save_memory(entry)
                assert success is True

                entries = load_all_memories()
                assert len(entries) == 1
                assert entries[0].task == "test task"
                assert entries[0].summary == "did something"
                assert "chose option A" in entries[0].decisions
            finally:
                os.chdir(original_cwd)

    def test_search_by_keyword(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                entry1 = MemoryEntry(task="add login feature", summary="implemented login")
                entry2 = MemoryEntry(task="add logout feature", summary="implemented logout")
                save_memory(entry1)
                save_memory(entry2)

                results = search_memories("login")
                assert len(results) == 1
                assert results[0].task == "add login feature"

                results = search_memories("logout")
                assert len(results) == 1
                assert results[0].task == "add logout feature"

                results = search_memories("nonexistent")
                assert len(results) == 0
            finally:
                os.chdir(original_cwd)

    def test_size_limit(self):
        test_dir = tempfile.mkdtemp()
        original_cwd = os.getcwd()
        try:
            os.chdir(test_dir)
            for i in range(20):
                entry = MemoryEntry(
                    id=str(uuid.uuid4()),
                    task=f"task_{i}",
                    summary="x" * 1000,
                )
                saved = save_memory(entry, max_total_size=5000)
                if not saved:
                    break
            else:
                pytest.fail("Should have hit size limit after multiple writes")
        finally:
            os.chdir(original_cwd)
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_format_for_context(self):
        entries = [
            MemoryEntry(
                task="add login",
                summary="implemented login page",
                decisions=["used JWT", "added rate limiting"],
            )
        ]
        formatted = format_memories_for_context(entries)
        assert "add login" in formatted
        assert "JWT" in formatted
        assert "rate limiting" in formatted

    def test_format_empty(self):
        assert format_memories_for_context([]) == ""

    def test_load_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                entries = load_all_memories()
                assert entries == []
            finally:
                os.chdir(original_cwd)
