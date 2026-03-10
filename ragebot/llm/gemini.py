"""
Gemini LLM Provider
────────────────────
Uses Gemini REST API directly (no SDK required).
API key is retrieved from the OS keyring (set via `rage auth`).
Supports all available Gemini models with comprehensive error handling.
"""
from __future__ import annotations

import json
import time
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from ragebot.llm.base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    """
    Gemini API provider using direct REST calls.
    No external dependencies required beyond Python stdlib.
    """
    
    # All available Gemini models as of March 2025
    AVAILABLE_MODELS = {
        # Gemini 2.0 models (latest)
        "gemini-2.0-flash-exp": "Experimental Flash 2.0",
        "gemini-2.0-flash-thinking-exp": "Experimental Flash 2.0 with thinking",
        
        # Gemini 1.5 models (stable)
        "gemini-1.5-pro": "Most capable 1.5 model",
        "gemini-1.5-pro-002": "Stable Pro version 002",
        "gemini-1.5-flash": "Fast and efficient",
        "gemini-1.5-flash-002": "Stable Flash version 002",
        "gemini-1.5-flash-8b": "Lightweight Flash variant",
        
        # Legacy models
        "gemini-1.0-pro": "Legacy 1.0 Pro model",
    }
    
    API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
    
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash") -> None:
        self._api_key = api_key
        self._model = model
        self._connection_tested = False
        
        # Validate model selection
        if model not in self.AVAILABLE_MODELS:
            print(f"⚠️  Warning: '{model}' not in known models. Using anyway...")
    
    @property
    def name(self) -> str:
        model_desc = self.AVAILABLE_MODELS.get(self._model, "Custom model")
        return f"Gemini ({self._model} - {model_desc})"
    
    def is_available(self) -> bool:
        """True when API key is set."""
        return bool(self._api_key)
    
    def _test_connection(self) -> tuple[bool, str]:
        """
        Test API connection and return (success, message).
        Only called once per instance.
        """
        if not self._api_key:
            return False, "No API key provided"
        
        try:
            # Simple test with minimal token usage
            url = f"{self.API_ENDPOINT}/{self._model}:generateContent?key={self._api_key}"
            
            payload = {
                "contents": [{
                    "parts": [{"text": "Hi"}]
                }],
                "generationConfig": {
                    "maxOutputTokens": 10
                }
            }
            
            req = Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            
            with urlopen(req, timeout=10) as response:
                response.read()
            
            return True, "✓ Connection successful"
            
        except HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get('error', {}).get('message', str(e))
            except:
                error_msg = str(e)
            
            if e.code == 400:
                return False, f"Invalid request: {error_msg}"
            elif e.code == 401 or e.code == 403:
                return False, f"Authentication failed: {error_msg}"
            elif e.code == 404:
                return False, f"Model '{self._model}' not found: {error_msg}"
            else:
                return False, f"HTTP {e.code}: {error_msg}"
                
        except URLError as e:
            return False, f"Network error: {e.reason}"
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"
    
    def _handle_api_error(self, error: HTTPError, attempt: int = 1) -> Optional[str]:
        """
        Handle API errors with appropriate messages and retry logic.
        Returns error message string, or None if should retry.
        """
        try:
            error_body = error.read().decode('utf-8', errors='replace')
            error_data = json.loads(error_body)
            error_msg = error_data.get('error', {}).get('message', 'Unknown error')
            error_status = error_data.get('error', {}).get('status', '')
        except:
            error_msg = str(error)
            error_status = ''
        
        # Rate limiting - attempt retry with exponential backoff
        if error.code == 429:
            if attempt <= 3:
                wait_time = 2 ** attempt  # 2, 4, 8 seconds
                print(f"⚠️  Rate limited. Retrying in {wait_time}s... (attempt {attempt}/3)")
                time.sleep(wait_time)
                return None  # Signal to retry
            else:
                return (
                    "❌ Rate limit exceeded. Please try again later.\n"
                    "Consider:\n"
                    "  • Waiting a few minutes before retrying\n"
                    "  • Using a different model\n"
                    "  • Checking your API quota at https://aistudio.google.com/app/apikey"
                )
        
        # Authentication errors
        if error.code in (401, 403):
            return (
                f"❌ Authentication failed: {error_msg}\n"
                "Please check:\n"
                "  • Your API key is correct\n"
                "  • The API key is enabled at https://aistudio.google.com/app/apikey\n"
                "  • You have access to the Gemini API\n"
                "Run:  rage auth  to update your credentials."
            )
        
        # Invalid request
        if error.code == 400:
            if "quota" in error_msg.lower() or "exceeded" in error_msg.lower():
                return (
                    f"❌ Quota exceeded: {error_msg}\n"
                    "Your API quota may be exhausted. Check:\n"
                    "  • https://aistudio.google.com/app/apikey\n"
                    "  • Consider upgrading your quota or trying tomorrow"
                )
            else:
                return f"❌ Invalid request: {error_msg}"
        
        # Model not found
        if error.code == 404:
            available = ", ".join(list(self.AVAILABLE_MODELS.keys())[:5])
            return (
                f"❌ Model not found: {self._model}\n"
                f"Available models include: {available}...\n"
                "See full list: https://ai.google.dev/models/gemini"
            )
        
        # Service unavailable
        if error.code in (500, 502, 503, 504):
            if attempt <= 2:
                wait_time = 3 * attempt
                print(f"⚠️  Service temporarily unavailable. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                return None  # Signal to retry
            else:
                return (
                    f"❌ Gemini service unavailable (HTTP {error.code})\n"
                    "The service may be experiencing issues. Please try again later."
                )
        
        # Generic error
        return f"❌ API error (HTTP {error.code}): {error_msg}"
    
    def complete(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        max_tokens: int = 1000,
        temperature: float = 1.0
    ) -> str:
        """
        Generate completion using Gemini API.
        
        Args:
            system_prompt: System instructions for the model
            user_prompt: User's input/question
            max_tokens: Maximum tokens to generate (default: 1000)
            temperature: Sampling temperature 0.0-2.0 (default: 1.0)
        
        Returns:
            Generated text response or error message
        """
        # Test connection on first use
        if not self._connection_tested:
            self._connection_tested = True
            success, message = self._test_connection()
            print(f"\n{message}\n")
            if not success:
                return f"{message}\n\nCannot proceed with generation."
        
        if not self._api_key:
            return "❌ No Gemini API key configured. Run:  rage auth  to set up your provider."
        
        # Build the full conversation
        # Gemini doesn't have a separate system role, so we include it in the first user message
        full_prompt = f"{system_prompt}\n\n{user_prompt}".strip()
        
        url = f"{self.API_ENDPOINT}/{self._model}:generateContent?key={self._api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": full_prompt}]
            }],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": max(0.0, min(2.0, temperature))  # Clamp to valid range
            }
        }
        
        # Retry logic for rate limits and transient errors
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                req = Request(
                    url,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}
                )
                
                with urlopen(req, timeout=60) as response:
                    result = json.loads(response.read().decode('utf-8'))
                
                # Extract the generated text
                candidates = result.get('candidates', [])
                if not candidates:
                    # Check for safety blocks or other issues
                    if 'promptFeedback' in result:
                        feedback = result['promptFeedback']
                        if feedback.get('blockReason'):
                            return f"⚠️  Content blocked: {feedback.get('blockReason')}"
                    return "⚠️  No response generated. The prompt may have been filtered."
                
                content = candidates[0].get('content', {})
                parts = content.get('parts', [])
                
                if not parts:
                    finish_reason = candidates[0].get('finishReason', 'UNKNOWN')
                    if finish_reason == 'SAFETY':
                        return "⚠️  Response blocked due to safety filters."
                    elif finish_reason == 'MAX_TOKENS':
                        return f"⚠️  Response truncated (hit {max_tokens} token limit). Try increasing max_tokens."
                    else:
                        return f"⚠️  Generation stopped: {finish_reason}"
                
                return parts[0].get('text', '').strip()
            
            except HTTPError as e:
                error_msg = self._handle_api_error(e, attempt)
                if error_msg is None:
                    # Retry signal
                    continue
                return error_msg
            
            except URLError as e:
                return f"❌ Network error: {e.reason}\nPlease check your internet connection."
            
            except json.JSONDecodeError as e:
                return f"❌ Failed to parse API response: {e}"
            
            except KeyError as e:
                return f"❌ Unexpected API response format: missing key {e}"
            
            except Exception as e:
                return f"❌ Unexpected error: {type(e).__name__}: {str(e)}"
        
        return "❌ Maximum retry attempts exceeded. Please try again later."


# Utility function to list available models
def list_available_models() -> None:
    """Print all available Gemini models."""
    print("Available Gemini Models:")
    print("=" * 60)
    for model, description in GeminiProvider.AVAILABLE_MODELS.items():
        print(f"  • {model:<35} {description}")
    print("=" * 60)


if __name__ == "__main__":
    # Example usage
    print("Gemini Provider - Standalone Test")
    print("=" * 60)
    
    # List models
    list_available_models()
    
    # Test with a dummy key (will fail but show error handling)
    print("\n\nTesting with invalid key (demonstrating error handling):")
    provider = GeminiProvider(api_key="test_key_123", model="gemini-1.5-flash")
    response = provider.complete(
        system_prompt="You are a helpful assistant.",
        user_prompt="Say hello!",
        max_tokens=50
    )
    print(f"\nResponse: {response}")