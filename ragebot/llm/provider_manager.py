# ragebot/llm/provider_manager.py
"""
Provider Manager - Dynamic provider/model management with centralized state.
Allows switching providers and models during runtime with validation.
"""
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

if TYPE_CHECKING:
    from ragebot.core.config import ConfigManager
    from ragebot.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class ProviderManager:
    """Centralized provider/model state management."""
    
    SUPPORTED_PROVIDERS = {
        "gemini": {
            "label": "Google Gemini",
            "icon": "✦",
            "color": "blue",
            "requires_key": True,
        },
        "groq": {
            "label": "Groq (OpenAI-Compatible)",
            "icon": "⚡",
            "color": "green",
            "requires_key": True,
        },
        "ollama": {
            "label": "Ollama (Local)",
            "icon": "🦙",
            "color": "yellow",
            "requires_key": False,
        },
        "none": {
            "label": "None (Context Retrieval Only)",
            "icon": "∅",
            "color": "white",
            "requires_key": False,
        },
    }
    
    PROVIDER_MODELS = {
        "gemini": [
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "desc": "Latest & fastest (recommended)"},
            {"id": "gemini-2.0-flash-lite", "name": "Gemini 2.0 Flash Lite", "desc": "Cost-efficient variant"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "desc": "Fast with 1M token context"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "desc": "Highest capability"},
        ],
        "groq": [
            {"id": "openai/gpt-oss-120b", "name": "GPT-OSS 120B", "desc": "Largest & most capable"},
            {"id": "llama-3.3-70b-versatile", "name": "LLaMA 3.3 70B", "desc": "Great for reasoning"},
            {"id": "llama-3.1-8b-instant", "name": "LLaMA 3.1 8B", "desc": "Ultra-fast"},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B", "desc": "MoE with 32k context"},
        ],
        "ollama": [
            # Dynamically populated from server
        ],
    }
    
    def __init__(self, config: "ConfigManager", console: Optional[Console] = None):
        self.config = config
        self.console = console or Console()
        self._current_provider = None
        self._current_model = None
        self._last_error: Optional[str] = None
    
    def get_current_provider(self) -> str:
        """Get the active provider name."""
        if self._current_provider is None:
            self._current_provider = self.config.get("llm_provider", "none")
        return self._current_provider
    
    def get_current_model(self) -> str:
        """Get the active model ID."""
        if self._current_model is None:
            provider = self.get_current_provider()
            self._current_model = self.config.get(
                f"{provider}_model",
                self._get_default_model(provider)
            )
        return self._current_model
    
    def _get_default_model(self, provider: str) -> str:
        """Get the default model for a provider."""
        defaults = {
            "gemini": "gemini-2.0-flash",
            "groq": "openai/gpt-oss-120b",
            "ollama": "llama3",
            "none": "",
        }
        return defaults.get(provider, "")
    
    def get_provider_instance(self) -> "BaseLLMProvider":
        """Get the current provider instance."""
        from ragebot.llm.factory import get_provider
        return get_provider(self.config)
    
    def list_available_models(self, provider: str) -> list[dict]:
        """Get available models for a provider."""
        if provider == "ollama":
            return self._discover_ollama_models()
        return self.PROVIDER_MODELS.get(provider, [])
    
    def _discover_ollama_models(self) -> list[dict]:
        """Discover available Ollama models."""
        try:
            import requests
            base_url = self.config.get("ollama_base_url", "http://localhost:11434")
            resp = requests.get(f"{base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            tags = resp.json().get("models", [])
            return [
                {
                    "id": tag["name"],
                    "name": tag["name"],
                    "desc": f"Ollama model: {tag['name']}",
                }
                for tag in tags
            ]
        except Exception as e:
            logger.error(f"Failed to discover Ollama models: {e}")
            return []
    
    def switch_provider(self, provider: str) -> bool:
        """Switch to a different provider. Returns True if successful."""
        if provider not in self.SUPPORTED_PROVIDERS:
            self._last_error = f"Unknown provider: {provider}"
            return False
        
        # Special handling for providers that require API keys
        provider_info = self.SUPPORTED_PROVIDERS[provider]
        if provider_info["requires_key"] and provider != "none":
            api_key = self.config.get(f"{provider}_api_key", "")
            if not api_key:
                self._last_error = f"No API key configured for {provider}. Run: rage auth login {provider}"
                return False
        
        try:
            self.config.set("llm_provider", provider)
            self._current_provider = provider
            self._current_model = None  # Reset model
            
            # Test connection
            instance = self.get_provider_instance()
            if not instance.is_available():
                self._last_error = f"Provider {provider} is not available"
                return False
            
            return True
        except Exception as e:
            self._last_error = str(e)
            return False
    
    def switch_model(self, model: str) -> bool:
        """Switch to a different model in the current provider."""
        provider = self.get_current_provider()
        
        # Validate model exists for this provider
        available = self.list_available_models(provider)
        if available and not any(m["id"] == model for m in available):
            self._last_error = f"Model '{model}' not available in {provider}"
            return False
        
        try:
            self.config.set(f"{provider}_model", model)
            self._current_model = model
            return True
        except Exception as e:
            self._last_error = str(e)
            return False
    
    def test_provider_connection(self) -> tuple[bool, str]:
        """Test if the current provider can be reached. Returns (success, message)."""
        provider = self.get_current_provider()
        instance = self.get_provider_instance()
        
        if not instance.is_available():
            return False, f"{provider} is not configured or API key is missing"
        
        try:
            # Perform a lightweight test call with a simple prompt
            response = instance.complete(
                system_prompt="You are a helpful assistant.",
                user_prompt="Reply with exactly: SUCCESS",
                max_tokens=50
            )
            
            # Validate we got a meaningful response
            if response and len(response.strip()) > 0:
                return True, f"✓ {provider} connection successful"
            else:
                return False, f"✗ {provider} returned empty response - verify API key and try again"
        except Exception as e:
            error_msg = str(e)
            # Extract the important part of the error message
            if "authentication" in error_msg.lower() or "401" in error_msg or "unauthorized" in error_msg.lower():
                return False, f"✗ {provider}: Invalid API key - {error_msg}"
            elif "rate" in error_msg.lower() or "429" in error_msg:
                return False, f"✗ {provider}: Rate limited - wait and try again"
            elif "connection" in error_msg.lower() or "network" in error_msg.lower():
                return False, f"✗ {provider}: Network error - check internet connection"
            else:
                return False, f"✗ {provider} error: {error_msg}"
    
    def display_provider_status(self) -> None:
        """Display current provider and model status."""
        current_provider = self.get_current_provider()
        current_model = self.get_current_model()
        
        table = Table(title="🔌 Current LLM Configuration", box=None, header_style="bold cyan")
        table.add_column("Setting", style="cyan", width=20)
        table.add_column("Value", style="green", width=40)
        
        provider_info = self.SUPPORTED_PROVIDERS.get(current_provider, {})
        table.add_row("Provider", f"{provider_info.get('label', current_provider)}")
        table.add_row("Model", current_model)
        
        instance = self.get_provider_instance()
        status = "✓ Available" if instance.is_available() else "✗ Not Available"
        table.add_row("Status", status)
        
        self.console.print(table)
    
    def display_all_providers(self) -> None:
        """Display all supported providers and their status."""
        table = Table(title="📋 Available Providers", box=None, header_style="bold cyan")
        table.add_column("Provider", style="cyan", width=15)
        table.add_column("Label", style="white", width=25)
        table.add_column("Status", style="green", width=20)
        table.add_column("Default Model", style="dim", width=30)
        
        current = self.get_current_provider()
        
        for provider_id, info in self.SUPPORTED_PROVIDERS.items():
            # Check if configured
            if provider_id == "none":
                status = "Ready (no LLM)"
            else:
                api_key = self.config.get(f"{provider_id}_api_key", "")
                status = "✓ Configured" if api_key else "○ Not Configured"
            
            display_name = provider_id
            if provider_id == current:
                display_name = f"★ {provider_id}"
            
            default_model = self._get_default_model(provider_id)
            table.add_row(display_name, info["label"], status, default_model)
        
        self.console.print(table)
    
    def display_models_for_provider(self, provider: str) -> None:
        """Display available models for a specific provider."""
        models = self.list_available_models(provider)
        if not models:
            self.console.print(f"[yellow]No models available for {provider}[/yellow]")
            return
        
        table = Table(title=f"📜 Models for {provider.title()}", box=None, header_style="bold cyan")
        table.add_column("Name", style="bold yellow", width=25)
        table.add_column("ID", style="dim", width=35)
        table.add_column("Description", style="white", width=30)
        
        current_model = self.get_current_model() if self.get_current_provider() == provider else ""
        
        for model in models:
            name = model["name"]
            if model["id"] == current_model:
                name = f"● {name}"
            table.add_row(name, f"[dim]{model['id']}[/dim]", model["desc"][:25])
        
        self.console.print(table)
    
    def get_last_error(self) -> Optional[str]:
        """Get the last error message."""
        return self._last_error
    
    def clear_error(self) -> None:
        """Clear the last error message."""
        self._last_error = None
