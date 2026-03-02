"""
LLM Factory — resolves the configured provider and returns a BaseLLMProvider.
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
            model=config.get("gemini_model", "gemini-1.5-flash"),
        )

    if provider_name == "grok":
        from ragebot.llm.grok import GrokProvider
        return GrokProvider(
            api_key=config.get("grok_api_key", ""),
            model=config.get("grok_model", "grok-3-mini"),
            base_url=config.get("grok_base_url", "https://api.x.ai/v1"),
        )

    # Fallback: no-op provider
    from ragebot.llm.noop import NoopProvider
    return NoopProvider()
