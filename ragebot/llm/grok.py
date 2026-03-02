"""
Grok LLM Provider (xAI)
────────────────────────
Grok exposes an OpenAI-compatible REST API endpoint at https://api.x.ai/v1.
We use the openai Python SDK pointing at that base URL so no extra dependency
is needed beyond `openai`.
API key is retrieved from the OS keyring (set via `rage auth login grok`).
"""
from __future__ import annotations

from ragebot.llm.base import BaseLLMProvider


class GrokProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "grok-3-mini",
        base_url: str = "https://api.x.ai/v1",
    ) -> None:
        self._api_key  = api_key
        self._model    = model
        self._base_url = base_url
        self._client   = None

    @property
    def name(self) -> str:
        return f"Grok/{self._model}"

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
            return f"[Grok error: {exc}]"
