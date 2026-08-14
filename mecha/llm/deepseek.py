"""DeepSeek LLM adapter — implements BaseLLM for DeepSeek API."""

import json
from openai import OpenAI
from mecha.llm.base import BaseLLM
from mecha.config import Config


SYSTEM_PROMPT = """You are Mecha, a helpful coding agent. You can chat naturally in Chinese AND execute coding actions.

When you need to execute an action (read file, write file, run command, mark complete), respond with ONLY a JSON object:
{
  "type": "read_file|write_file|run_command|complete",
  "params": {
    "path": "relative/path",
    "content": "file content",
    "command": "shell command",
    "summary": "task summary"
  },
  "reasoning": "why you are doing this"
}

When you just want to chat, reply in plain Chinese text — no JSON needed.

IMPORTANT RULES:
- Communicate in Chinese for all chat replies, reasoning, and summaries.
- Use read_file to understand existing code before modifying it.
- Use write_file to create or modify files. Always write complete file content.
- Use run_command for testing (pytest), linting, or git operations.
- Use complete when the task is fully done. Include a summary of what you did.
- Always run tests after writing code to verify correctness.
- If tests fail, read the error output, fix the code, and run tests again.
- Do NOT invent file contents — read files first.
- Paths are relative to the project root.
- Shell commands must be safe and non-destructive."""


class DeepSeekLLM(BaseLLM):
    """LLM adapter for DeepSeek API via OpenAI-compatible SDK."""

    def __init__(self, config: Config, api_key: str):
        self.config = config
        self.client = OpenAI(
            api_key=api_key,
            base_url=config.llm_base_url,
            timeout=config.llm_timeout,
        )
        # Token usage tracking
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def chat(self, messages: list[dict]) -> str:
        """Send messages to DeepSeek and return the response text."""
        response = self.client.chat.completions.create(
            model=self.config.llm_model,
            messages=messages,
            max_tokens=4096,
        )
        # Track token usage
        if hasattr(response, "usage") and response.usage:
            self.last_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            self.total_prompt_tokens += response.usage.prompt_tokens
            self.total_completion_tokens += response.usage.completion_tokens
            self.total_tokens += response.usage.total_tokens
        return response.choices[0].message.content or ""

    def build_initial_messages(self, task: str, context: str) -> list[dict]:
        """Build the initial message list for a new task."""
        user_message = f"## Task\n{task}\n\n## Context\n{context}"
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
