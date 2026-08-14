"""Configuration module — parses .mecha.yaml with sensible defaults."""

import os
import yaml
from dataclasses import dataclass, field


@dataclass
class Config:
    """Mecha configuration loaded from .mecha.yaml."""
    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-chat"
    llm_base_url: str = "https://api.deepseek.com"
    max_iterations: int = 20
    llm_timeout: int = 60
    max_retries: int = 3
    max_fix_rounds: int = 3
    max_file_size: int = 1_048_576  # 1MB
    memory_max_size: int = 102_400  # 100KB
    guardrail_rules_path: str = ""
    tool_whitelist: list = field(default_factory=lambda: ["read_file", "write_file", "run_command"])
    custom_danger_rules: list = field(default_factory=list)
    custom_confirm_rules: list = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str = ".mecha.yaml") -> "Config":
        """Load configuration from a YAML file. Returns defaults if file missing."""
        if not os.path.exists(path):
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Create Config from a dict (for testing)."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})