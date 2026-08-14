"""Unit tests for Config module."""

import pytest
import tempfile
import os
from mecha.config import Config


class TestConfig:
    def test_defaults(self):
        config = Config()
        assert config.llm_provider == "deepseek"
        assert config.max_iterations == 20
        assert config.max_file_size == 1_048_576

    def test_from_file_missing(self):
        config = Config.from_file("/nonexistent/path.yaml")
        assert config.llm_provider == "deepseek"

    def test_from_file_with_values(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, ".mecha.yaml")
            with open(path, "w") as f:
                f.write("llm_provider: openai\nmax_iterations: 10\n")

            config = Config.from_file(path)
            assert config.llm_provider == "openai"
            assert config.max_iterations == 10
            # Unspecified values use defaults
            assert config.llm_model == "deepseek-chat"

    def test_from_file_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, ".mecha.yaml")
            with open(path, "w") as f:
                f.write("")

            config = Config.from_file(path)
            assert config.llm_provider == "deepseek"

    def test_from_dict(self):
        config = Config.from_dict({"llm_provider": "openai", "max_iterations": 5})
        assert config.llm_provider == "openai"
        assert config.max_iterations == 5