"""
Gemini LLM Provider
────────────────────
Uses google-generativeai SDK.
API key is retrieved from the OS keyring (set via `rage auth login gemini`).
Falls back gracefully when the SDK is not installed.
"""
from __future__ import annotations

from ragebot.llm.base import BaseLLMProvider

_SDK_AVAILABLE: bool | None = None  # lazily checked


def _check_sdk() -> bool:
    global _SDK_AVAILABLE
    if _SDK_AVAILABLE is None:
        try:
            import google.generativeai  # type: ignore  # noqa: F401
            _SDK_AVAILABLE = True
        except ImportError:
            _SDK_AVAILABLE = False
    return _SDK_AVAILABLE


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash") -> None:
        self._api_key = api_key
        self._model   = model
        self._client  = None

    @property
    def name(self) -> str:
        return f"Gemini ({self._model})"

    def is_available(self) -> bool:
        """True only when both the SDK is installed AND a key is set."""
        return bool(self._api_key) and _check_sdk()

    def _get_client(self):
        if self._client is None:
            if not _check_sdk():
                raise RuntimeError(
                    "google-generativeai is not installed. "
                    "Run:  pip install google-generativeai  or  pip install 'ragebot-mcp[gemini]'"
                )
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=self._api_key)
            self._client = genai.GenerativeModel(self._model)
        return self._client

    def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 1000) -> str:
        if not _check_sdk():
            return (
                "⚠️  Gemini SDK not installed.\n"
                "Run:  pip install google-generativeai  or  pip install 'ragebot-mcp[gemini]'"
            )
        if not self._api_key:
            return "⚠️  No Gemini API key. Run:  rage auth login gemini"
        client = self._get_client()
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        try:
            response = client.generate_content(
                full_prompt,
                generation_config={"max_output_tokens": max_tokens},
            )
            return response.text
        except Exception as exc:
            return f"[Gemini error: {exc}]"
