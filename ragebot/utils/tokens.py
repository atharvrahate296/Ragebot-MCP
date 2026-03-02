"""
Token Counter - Estimates token usage for text.
Uses tiktoken if available, else approximates.
"""
from __future__ import annotations


class TokenCounter:
    def __init__(self, model: str = "gpt-4o"):
        self._encoder = None
        self._model = model
        self._tried_import = False

    @property
    def encoder(self):
        if self._encoder is None and not self._tried_import:
            self._tried_import = True
            try:
                import tiktoken
                self._encoder = tiktoken.encoding_for_model(self._model)
            except (ImportError, KeyError):
                try:
                    import tiktoken
                    self._encoder = tiktoken.get_encoding("cl100k_base")
                except ImportError:
                    self._encoder = None
        return self._encoder

    def count(self, text: str) -> int:
        """Count tokens in text."""
        if not text:
            return 0
        if self.encoder:
            return len(self.encoder.encode(text))
        # Fallback: approximate (1 token ≈ 4 chars)
        return len(text) // 4

    def truncate(self, text: str, max_tokens: int) -> str:
        """Truncate text to max_tokens."""
        if self.count(text) <= max_tokens:
            return text
        if self.encoder:
            tokens = self.encoder.encode(text)[:max_tokens]
            return self.encoder.decode(tokens)
        # Approximate
        return text[: max_tokens * 4]

    def estimate_cost(self, tokens: int, model: str = "gpt-4o-mini") -> float:
        """Estimate API cost in USD."""
        pricing = {
            "gpt-4o": 0.000005,
            "gpt-4o-mini": 0.0000002,
            "gpt-4": 0.00003,
            "claude-3-5-haiku-20241022": 0.0000008,
            "claude-3-5-sonnet-20241022": 0.000003,
        }
        rate = pricing.get(model, 0.000002)
        return tokens * rate
