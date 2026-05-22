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
from ragebot.utils.logging_config import BackgroundTaskLogger

logger = logging.getLogger(__name__)
_ollama_log = BackgroundTaskLogger("ollama")



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
        _ollama_log.info(f"Discovering models from {self.base_url}/api/tags")
        try:
            resp = requests.get(
                f"{self.base_url}/api/tags",
                timeout=self.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            tags = resp.json().get("models", [])

            if not tags:
                self.MODELS = []
                _ollama_log.warning(
                    "No models found on the Ollama server. "
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
            _ollama_log.info(f"Discovered {len(self.MODELS)} models")

        except requests.ConnectionError as e:
            _ollama_log.error(f"Cannot connect to Ollama at {self.base_url}")
            self.MODELS = []
            raise RuntimeError(
                f"Ollama server not running at {self.base_url}. "
                f"Start it with: ollama serve"
            ) from e
        except requests.Timeout as e:
            _ollama_log.error(f"Request timeout while connecting to {self.base_url}")
            self.MODELS = []
            raise RuntimeError(
                f"Ollama server at {self.base_url} is not responding. "
                f"Make sure it's running and accessible."
            ) from e
        except requests.RequestException as e:
            _ollama_log.error(f"Failed to fetch models: {e}")
            self.MODELS = []
            raise RuntimeError(f"Failed to connect to Ollama: {e}") from e
        except (KeyError, ValueError) as e:
            _ollama_log.error(f"Invalid response format from API: {e}")
            self.MODELS = []
            raise RuntimeError(f"Invalid response from Ollama API: {e}") from e

    @property
    def name(self) -> str:
        """Return the provider name."""
        return "ollama"

    def is_available(self) -> bool:
        """Check if the Ollama server is reachable and has models available."""
        from ragebot.utils.error_handler import RageBotError
        
        try:
            resp = requests.head(
                f"{self.base_url}/api/tags",
                timeout=self.REQUEST_TIMEOUT,
            )
            return resp.status_code == 200 and len(self.MODELS) > 0
        except requests.ConnectionError:
            logger.warning(f"Ollama server not reachable at {self.base_url}")
            return False
        except requests.Timeout:
            logger.warning(f"Ollama server timeout at {self.base_url}")
            return False
        except Exception as e:
            logger.warning(f"Failed to check Ollama availability: {e}")
            return False

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1000,
    ) -> str:
        """Generate a text completion using the Ollama model.
        
        Raises:
            RageBotError: On connection failure or model errors
        """
        from ragebot.utils.error_handler import RageBotError, ErrorCategory, ErrorSeverity
        
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
            
            # Validate response structure
            if not response.choices or not response.choices[0].message.content:
                raise RageBotError(
                    "Ollama returned empty response",
                    category=ErrorCategory.PROVIDER_FAILURE,
                    severity=ErrorSeverity.ERROR,
                    recovery_steps=[
                        f"Check model is running: ollama list",
                        f"Try switching provider: rage auth",
                    ],
                )
            
            return response.choices[0].message.content
        
        except RageBotError:
            raise
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Ollama completion failed: {e}")
            
            # Model not found or endpoint unreachable
            if "404" in error_msg or "not found" in error_msg.lower():
                raise RageBotError(
                    f"Ollama model '{self.model}' not found or endpoint unreachable",
                    category=ErrorCategory.PROVIDER_FAILURE,
                    severity=ErrorSeverity.ERROR,
                    recovery_steps=[
                        "1. Verify Ollama is running: ollama serve",
                        f"2. Check model is installed: ollama list",
                        f"3. Pull the model if needed: ollama pull {self.model}",
                        "4. Try switching provider: rage auth",
                    ],
                ) from e
            
            # Connection failures
            if "connection" in error_msg.lower() or "refused" in error_msg.lower() or "unreachable" in error_msg.lower():
                raise RageBotError(
                    f"Cannot connect to Ollama server at {self.base_url}",
                    category=ErrorCategory.NETWORK,
                    severity=ErrorSeverity.ERROR,
                    recovery_steps=[
                        "1. Start Ollama: ollama serve",
                        f"2. Check it's running on the correct port (default: 11434)",
                        "3. Verify base_url is correct",
                        "4. Try switching provider: rage auth",
                    ],
                ) from e
            
            # Timeout
            if "timeout" in error_msg.lower():
                raise RageBotError(
                    f"Ollama request timed out",
                    category=ErrorCategory.NETWORK,
                    severity=ErrorSeverity.ERROR,
                    recovery_steps=[
                        "1. Check if Ollama server is responsive",
                        "2. Try a smaller model for faster responses",
                        "3. Increase timeout if needed",
                    ],
                ) from e
            
            # Generic error
            raise RageBotError(
                f"Ollama API error: {error_msg}",
                category=ErrorCategory.PROVIDER_FAILURE,
                severity=ErrorSeverity.ERROR,
                context={"error_type": type(e).__name__, "model": self.model},
            ) from e