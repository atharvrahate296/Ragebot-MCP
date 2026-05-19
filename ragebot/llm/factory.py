"""
LLM Factory — resolves the configured provider and returns a BaseLLMProvider.

Updated with Ollama provider support:
✓ Detects Ollama provider configuration
✓ Routes to OllamaProvider
✓ Maintains isolation between providers
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ragebot.core.config import ConfigManager
    from ragebot.llm.base import BaseLLMProvider


def get_provider(config: "ConfigManager") -> "BaseLLMProvider":
    """Return the active LLM provider based on config."""
    provider_name = config.get("llm_provider", "none").lower()

    if provider_name == "gemini":
        from ragebot.llm.gemini import GeminiProvider
        return GeminiProvider(
            api_key=config.get("gemini_api_key", ""),
            model=config.get("gemini_model", "gemini-2.0-flash"),
        )

    if provider_name == "groq":
        from ragebot.llm.groq import GroqProvider
        return GroqProvider(
            api_key=config.get("groq_api_key", ""),
            model=config.get("groq_model", "openai/gpt-oss-120b"),
            base_url=config.get("groq_base_url", "https://api.groq.com/openai/v1"),
        )

    if provider_name == "ollama":
        from ragebot.llm.ollama import OllamaProvider
        return OllamaProvider(
            model=config.get("ollama_model", "llama3"),
            base_url=config.get("ollama_base_url", "http://localhost:11434"),
        )

    # Fallback: no-op provider
    from ragebot.llm.noop import NoopProvider
    return NoopProvider()
