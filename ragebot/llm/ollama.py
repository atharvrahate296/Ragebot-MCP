# ragebot/llm/ollama.py
"""
Ollama LLM Provider
────────────────────
The provider talks to a locally running Ollama server at
http://localhost:11434 (the default Ollama HTTP API endpoint). It uses
the OpenAI-compatible wrapper from `openai` but points to the
Ollama endpoint. The list of models is discovered at runtime and
cached in `OllamaProvider.MODELS`.

No API key is required for Ollama as it runs locally.

Author: OpenAI-style adaptation
"""

from __future__ import annotations

import logging
from typing import TypedDict

import requests
from openai import OpenAI

from ragebot.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class ModelInfo(TypedDict):
    """Type definition for model information."""
    id: str
    name: str
    description: str


class OllamaProvider(BaseLLMProvider):
    """
    Provider for a locally running Ollama instance.

    The constructor fetches available models via the `/api/tags` endpoint
    and validates that Ollama is running and has models installed.
    
    No API key is required for Ollama as it runs locally.
    """

    # Class-level cache to avoid repeated HTTP calls across instances
    MODELS: list[ModelInfo] = []
    
    DEFAULT_BASE_URL: str = "http://localhost:11434"
    DEFAULT_MODEL: str = "llama3"
    REQUEST_TIMEOUT: float = 5.0

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        """
        Initialize the Ollama provider for local LLM inference.

        Args:
            model: Model name to use (default: llama3). Auto-discovered from available models.
            base_url: Base URL of the Ollama server (default: http://localhost:11434).
        
        Raises:
            RuntimeError: If Ollama server is not running or no models are available.
        """
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = None
        
        # Fetch and validate model list
        self._discover_models()
        
        # Verify that at least one model is available
        if not self.MODELS:
            raise RuntimeError(
                "Ollama Error: No models installed.\n"
                "Please install a model using: ollama pull <model_name>\n"
                "Example: ollama pull llama3"
            )
        
        # Validate selected model exists
        available_model_names = [m["id"] for m in self.MODELS]
        if model not in available_model_names:
            logger.warning(
                f"Model '{model}' not found. Available models: {', '.join(available_model_names)}. "
                f"Using first available: {available_model_names[0]}"
            )
            self.model = available_model_names[0]
        
        # Create OpenAI client pointing to Ollama's OpenAI-compatible endpoint
        try:
            self.client = OpenAI(api_key="ollama", base_url=f"{self.base_url}/v1")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Ollama client: {e}") from e

    def _discover_models(self) -> None:
        """
        Fetch and cache available models from the Ollama API.

        Populates `MODELS` with the list of tags returned by the Ollama API's
        `/api/tags` endpoint. Raises an error if the server is not running.
        """
        try:
            resp = requests.get(
                f"{self.base_url}/api/tags",
                timeout=self.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            tags = resp.json().get("models", [])
            
            if not tags:
                self.MODELS = []
                logger.error(
                    "Ollama Error: No models found on the server. "
                    "Install models using: ollama pull <model_name>"
                )
                return
            
            self.MODELS = [
                {
                    "id": tag["name"],
                    "name": tag["name"],
                    "description": f"Ollama model: {tag['name']}",
                }
                for tag in tags
            ]
            logger.info(f"Discovered {len(self.MODELS)} Ollama models: {', '.join(m['id'] for m in self.MODELS)}")
            
        except requests.ConnectionError as e:
            logger.error(
                f"Ollama Error: Cannot connect to Ollama server at {self.base_url}\n"
                f"Make sure Ollama is running: ollama serve"
            )
            self.MODELS = []
            raise RuntimeError(
                f"Ollama server not running at {self.base_url}. "
                f"Start it with: ollama serve"
            ) from e
        except requests.Timeout as e:
            logger.error(f"Ollama Error: Request timeout while connecting to {self.base_url}")
            self.MODELS = []
            raise RuntimeError(
                f"Ollama server at {self.base_url} is not responding. "
                f"Make sure it's running and accessible."
            ) from e
        except requests.RequestException as e:
            logger.error(f"Ollama Error: Failed to fetch models: {e}")
            self.MODELS = []
            raise RuntimeError(f"Failed to connect to Ollama: {e}") from e
        except (KeyError, ValueError) as e:
            logger.error(f"Ollama Error: Invalid response format from API: {e}")
            self.MODELS = []
            raise RuntimeError(f"Invalid response from Ollama API: {e}") from e

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "ollama"

    def is_available(self) -> bool:
        """Check if the Ollama server is reachable and has models available."""
        try:
            resp = requests.head(
                f"{self.base_url}/api/tags",
                timeout=self.REQUEST_TIMEOUT,
            )
            return resp.status_code == 200 and len(self.MODELS) > 0
        except requests.RequestException:
            return False

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1000,
    ) -> str:
        """Generate a text completion using the Ollama model."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ollama completion failed: {e}")
            if "404" in error_msg:
                return (
                    f"[Ollama error] Model '{self.model}' not found or endpoint unreachable.\n"
                    "Recovery steps:\n"
                    "  1. Verify Ollama is running: ollama serve\n"
                    f"  2. Check model is installed: ollama list\n"
                    f"  3. Pull the model if needed: ollama pull {self.model}\n"
                    "  4. Try switching provider: rage auth"
                )
            if "connection" in error_msg.lower() or "refused" in error_msg.lower():
                return (
                    "[Ollama error] Cannot connect to Ollama server.\n"
                    "Recovery steps:\n"
                    "  1. Start Ollama: ollama serve\n"
                    "  2. Check it's running on the correct port (default: 11434)\n"
                    "  3. Try switching provider: rage auth"
                )
            return f"[Ollama error: {e}]"