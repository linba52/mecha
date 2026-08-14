"""LLM abstraction layer — BaseLLM interface."""

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """Abstract base class for LLM providers.

    All LLM implementations (real or mock) must implement chat().
    """

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        """Send messages to the LLM and return the response text.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.

        Returns:
            The LLM's response as a string.
        """
        ...