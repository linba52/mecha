"""DeepSeek LLM adapter — implements BaseLLM for DeepSeek API."""

import json
from openai import OpenAI
from mecha.llm.base import BaseLLM
from mecha.config import Config


SYSTEM_PROMPT = """You are Mecha, a coding agent. You complete coding tasks by:

1. Reading files with read_file
2. Writing code with write_file
3. Running commands with run_command
4. Marking completion with complete

Respond ONLY with a JSON object in this exact format:
{
  "type": "read_file|write_file|run_command|complete",
  "params": {
    "path": "relative/path" (for read_file/write_file),
    "content": "file content" (for write_file),
    "command": "shell command" (for run_command),
    "summary": "what was done" (for complete)
  },
  "reasoning": "why you are doing this action"
}

IMPORTANT RULES:
- Use Chinese to communicate. All reasoning and summary fields must be in Chinese.
- Use read_file to understand existing code before modifying it
- Use write_file to create or modify files. Always write complete file content.
- Use run_command for testing (pytest), linting, or git operations
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

    def chat(self, messages: list[dict]) -> str:
        """Send messages to DeepSeek and return the response text."""
        response = self.client.chat.completions.create(
            model=self.config.llm_model,
            messages=messages,
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""

    def build_initial_messages(self, task: str, context: str) -> list[dict]:
        """Build the initial message list for a new task."""
        user_message = f"## Task\n{task}\n\n## Context\n{context}"
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
