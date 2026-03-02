"""
Abstract LLM provider base class.
"""
from __future__ import annotations
from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """All LLM providers must implement this interface."""

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 1000) -> str:
        """Return a text completion."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider has a valid API key configured."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""
