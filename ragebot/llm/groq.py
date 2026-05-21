"""
Groq LLM Provider
──────────────────
Groq exposes an OpenAI-compatible REST API endpoint at https://api.groq.com/openai/v1.
We use the openai Python SDK pointing at that base URL so no extra dependency
is needed beyond `openai`.
API key is retrieved from the OS keyring (set via `rage auth`).
"""
from __future__ import annotations

from ragebot.llm.base import BaseLLMProvider


class GroqProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-oss-120b",
        base_url: str = "https://api.groq.com/openai/v1",
    ) -> None:
        self._api_key  = api_key
        self._model    = model
        self._base_url = base_url
        self._client   = None

    @property
    def name(self) -> str:
        return f"Groq/{self._model}"

    def is_available(self) -> bool:
        return bool(self._api_key)

    def _get_client(self):
        if self._client is None:
            try:
                import openai                               # type: ignore
                self._client = openai.OpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                )
            except ImportError as exc:
                raise RuntimeError(
                    "openai package is not installed. Run: pip install openai"
                ) from exc
        return self._client

    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 1000) -> str:
        client = self._get_client()
        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            error_msg = str(exc)
            if "rate_limit" in error_msg.lower() or "429" in error_msg:
                return (
                    "❌ Groq rate limit exceeded.\n"
                    "Recovery steps:\n"
                    "  1. Wait a few moments and try again\n"
                    "  2. Switch to a different model: rage model\n"
                    "  3. Switch provider: rage auth"
                )
            if "401" in error_msg or "auth" in error_msg.lower() or "invalid" in error_msg.lower():
                return (
                    "❌ Groq authentication failed.\n"
                    "Recovery steps:\n"
                    "  1. Check your API key: rage auth\n"
                    "  2. Get a new key at: https://console.groq.com/keys"
                )
            if "connection" in error_msg.lower() or "network" in error_msg.lower():
                return (
                    "❌ Cannot reach Groq API.\n"
                    "Recovery steps:\n"
                    "  1. Check your internet connection\n"
                    "  2. Try again in a moment\n"
                    "  3. Switch provider: rage auth"
                )
            return f"[Groq error: {exc}]"
