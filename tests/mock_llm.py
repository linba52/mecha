"""Mock LLM for deterministic testing — implements BaseLLM interface."""

from mecha.llm.base import BaseLLM


class MockLLM(BaseLLM):
    """A mock LLM that returns preset responses in sequence.

    Used for deterministic unit testing of harness mechanisms
    without requiring network access or a real LLM.
    """

    def __init__(self, responses: list[str] | None = None):
        """Initialize with a list of preset responses.

        Args:
            responses: List of response strings to return in order.
                       Each call to chat() returns the next response.
        """
        self.responses = responses or []
        self.call_count = 0
        self.call_history: list[list[dict]] = []

    def chat(self, messages: list[dict]) -> str:
        """Return the next preset response.

        Raises IndexError if called more times than available responses.
        """
        self.call_history.append(messages)
        if self.call_count >= len(self.responses):
            raise IndexError(
                f"MockLLM called {self.call_count + 1} times but only "
                f"{len(self.responses)} responses configured"
            )
        response = self.responses[self.call_count]
        self.call_count += 1
        return response

    def add_response(self, response: str) -> None:
        """Add a response to the end of the queue."""
        self.responses.append(response)