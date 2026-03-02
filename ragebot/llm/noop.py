"""No-op provider used when no LLM is configured."""
from ragebot.llm.base import BaseLLMProvider


class NoopProvider(BaseLLMProvider):
    @property
    def name(self) -> str:
        return "none"

    def is_available(self) -> bool:
        return False

    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 1000) -> str:
        return (
            "⚠️  No LLM provider configured. "
            "Run `rage auth login gemini` or `rage auth login grok` to set up a provider."
        )
