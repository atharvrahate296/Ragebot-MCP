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
from ragebot.utils.error_handler import RageBotError, ErrorCategory, ErrorSeverity


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
                    timeout=10.0,
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
            
            # Validate response structure
            if not response.choices or not response.choices[0].message.content:
                raise RageBotError(
                    "Groq API returned empty response",
                    category=ErrorCategory.PROVIDER_FAILURE,
                    severity=ErrorSeverity.ERROR,
                    recovery_steps=[
                        "Check your API key validity",
                        "Try again: rage auth login groq",
                        "Check Groq service status",
                    ],
                )
            
            return response.choices[0].message.content
        except RageBotError:
            raise
        except Exception as exc:
            import openai  # type: ignore
            msg = str(exc)
            exc_type = type(exc).__name__
            
            # Handle specific OpenAI library exceptions
            if isinstance(exc, openai.AuthenticationError) or "401" in msg or "authentication" in msg.lower() or "unauthorized" in msg.lower():
                raise RageBotError(
                    "Groq authentication failed - invalid API key",
                    category=ErrorCategory.AUTHENTICATION,
                    severity=ErrorSeverity.ERROR,
                    recovery_steps=[
                        "Verify your API key at: https://console.groq.com/keys",
                        "Re-authenticate: rage auth login groq",
                        "Ensure key has proper permissions",
                    ],
                    context={"provider": "groq", "error_type": exc_type},
                ) from exc
            if isinstance(exc, openai.RateLimitError) or "rate_limit" in msg.lower() or "429" in msg:
                raise RageBotError(
                    "Groq rate limit exceeded",
                    category=ErrorCategory.RATE_LIMIT,
                    severity=ErrorSeverity.WARNING,
                    recovery_steps=[
                        "Wait a moment and retry",
                        "Switch to a smaller model: rage model",
                    ],
                    context={"provider": "groq", "model": self._model},
                ) from exc
            if isinstance(exc, openai.APIConnectionError) or "connection" in msg.lower() or "network" in msg.lower():
                raise RageBotError(
                    f"Groq connection failed",
                    category=ErrorCategory.NETWORK,
                    severity=ErrorSeverity.ERROR,
                    recovery_steps=[
                        "Check your internet connection",
                        "Try again in a moment",
                        "Verify Groq API is accessible: https://api.groq.com",
                    ],
                    context={"provider": "groq", "error_type": exc_type},
                ) from exc
            raise RageBotError(
                f"Groq API error: {exc}",
                category=ErrorCategory.PROVIDER_FAILURE,
                severity=ErrorSeverity.ERROR,
                context={"provider": "groq", "error_type": exc_type, "model": self._model},
            ) from exc
