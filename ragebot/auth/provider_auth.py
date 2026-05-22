# ragebot/auth/provider_auth.py
"""
Provider Authentication - Enhanced auth system with validation & connection testing.
Includes masked API key input, automatic connection tests, and clear feedback.
"""
from __future__ import annotations

import getpass
from typing import Optional, TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

if TYPE_CHECKING:
    from ragebot.core.config import ConfigManager
    from ragebot.llm.provider_manager import ProviderManager


class ProviderAuthenticator:
    """Handle provider authentication with validation and testing."""
    
    def __init__(self, config: "ConfigManager", provider_mgr: "ProviderManager", 
                 console: Optional[Console] = None):
        self.config = config
        self.provider_mgr = provider_mgr
        self.console = console or Console()
    
    def authenticate_provider(self, provider: str) -> tuple[bool, str]:
        """
        Authenticate a provider with full validation flow.
        Returns (success, message).
        """
        if provider == "ollama":
            return self._auth_ollama()
        elif provider == "gemini":
            return self._auth_gemini()
        elif provider == "groq":
            return self._auth_groq()
        else:
            return False, f"Unknown provider: {provider}"
    
    def _mask_api_key_input(self, prompt_text: str = "API Key") -> str:
        """
        Read API key with masking (password-style input).
        Returns the unmasked key.
        """
        self.console.print(f"\n[dim]Your API key will be masked and stored securely in OS keyring.[/dim]")
        key = getpass.getpass(f"{prompt_text}: ")
        return key.strip()
    
    def _auth_gemini(self) -> tuple[bool, str]:
        """Authenticate with Google Gemini."""
        self.console.print(Panel(
            "[bold cyan]Google Gemini Authentication[/bold cyan]\n\n"
            "[dim]Get a free API key at: https://aistudio.google.com/apikey[/dim]",
            border_style="cyan",
            padding=(1, 2)
        ))
        
        api_key = self._mask_api_key_input("Gemini API Key")

        if not api_key:
            return False, "No API key provided."

        # Store the key
        self.config.set("gemini_api_key", api_key)

        # Test connection with Live spinner
        from rich.live import Live
        from rich.spinner import Spinner
        self.console.print()
        with Live(
            Spinner("dots", text="[cyan]Testing gemini connection…[/cyan]"),
            refresh_per_second=10,
            transient=True,
        ):
            success, msg = self.provider_mgr.test_provider_for_auth("gemini")

        if success:
            self.console.print(
                Panel(
                    "[bold green]✓  Connected to Gemini[/bold green]",
                    border_style="green", padding=(0, 2), expand=False,
                )
            )
        else:
            self.console.print(
                Panel(
                    f"[bold red]✗  Connection failed[/bold red]\n"
                    f"[dim]{msg}[/dim]\n\n"
                    f"[yellow]💡 The API key has been saved, but we couldn't verify it.[/yellow]\n"
                    f"Check your key or network connection.",
                    border_style="red", padding=(1, 2),
                )
            )
            if not Confirm.ask("[bold]Continue with this provider anyway?[/bold]", default=True):
                self.config.delete_secret("gemini_api_key")
                return False, "Authentication cancelled by user."

        # Let user select a model
        models = self.provider_mgr.list_available_models("gemini")
        if models:
            self.console.print(Panel(
                "[bold]Select a Gemini model:[/bold]",
                border_style="cyan",
                padding=(0, 2)
            ))
            for i, m in enumerate(models, 1):
                self.console.print(f"  {i}. {m['name']:<30} ({m['id']})")
            
            try:
                choice = self.console.input("\n[bold]Select model (number, default 1):[/bold] ").strip()
                if not choice:
                    choice_idx = 0
                else:
                    choice_idx = int(choice) - 1
                
                if 0 <= choice_idx < len(models):
                    selected = models[choice_idx]
                    self.config.set("gemini_model", selected["id"])
                    self.config.set("llm_provider", "gemini")
                    return True, (
                        f"✓ Gemini configured successfully\n"
                        f"[green]Model: {selected['name']}[/green]"
                    )
            except (ValueError, IndexError):
                self.console.print("[yellow]Invalid choice, using default model.[/yellow]")
        
        # Fallback: use default model
        self.config.set("llm_provider", "gemini")
        return True, "✓ Gemini configured successfully (using default model)"

    
    def _auth_groq(self) -> tuple[bool, str]:
        """Authenticate with Groq (OpenAI-compatible API)."""
        self.console.print(Panel(
            "[bold green]Groq Authentication[/bold green]\n\n"
            "[dim]Get an API key at: https://console.groq.com/keys[/dim]",
            border_style="green",
            padding=(1, 2)
        ))
        
        api_key = self._mask_api_key_input("Groq API Key")

        if not api_key:
            return False, "No API key provided."

        # Store the key
        self.config.set("groq_api_key", api_key)

        # Test connection with Live spinner
        from rich.live import Live
        from rich.spinner import Spinner
        self.console.print()
        with Live(
            Spinner("dots", text="[cyan]Testing groq connection…[/cyan]"),
            refresh_per_second=10,
            transient=True,
        ):
            success, msg = self.provider_mgr.test_provider_for_auth("groq")

        if success:
            self.console.print(
                Panel(
                    "[bold green]✓  Connected to Groq[/bold green]",
                    border_style="green", padding=(0, 2), expand=False,
                )
            )
        else:
            self.console.print(
                Panel(
                    f"[bold red]✗  Connection failed[/bold red]\n"
                    f"[dim]{msg}[/dim]\n\n"
                    f"[yellow]💡 The API key has been saved, but we couldn't verify it.[/yellow]\n"
                    f"Check your key or network connection.",
                    border_style="red", padding=(1, 2),
                )
            )
            if not Confirm.ask("[bold]Continue with this provider anyway?[/bold]", default=True):
                self.config.delete_secret("groq_api_key")
                return False, "Authentication cancelled by user."

        # Select model
        models = self.provider_mgr.list_available_models("groq")
        if models:
            self.console.print(Panel(
                "[bold]Select a Groq model:[/bold]",
                border_style="green",
                padding=(0, 2)
            ))
            for i, m in enumerate(models, 1):
                self.console.print(f"  {i}. {m['name']:<30} ({m['id']})")
            
            try:
                choice = self.console.input("\n[bold]Select model (number, default 1):[/bold] ").strip()
                if not choice:
                    choice_idx = 0
                else:
                    choice_idx = int(choice) - 1
                
                if 0 <= choice_idx < len(models):
                    selected = models[choice_idx]
                    self.config.set("groq_model", selected["id"])
                    self.config.set("llm_provider", "groq")
                    return True, (
                        f"✓ Groq configured successfully\n"
                        f"[green]Model: {selected['name']}[/green]"
                    )
            except (ValueError, IndexError):
                self.console.print("[yellow]Invalid choice, using default model.[/yellow]")
        
        self.config.set("llm_provider", "groq")
        return True, "✓ Groq configured successfully"
    
    def _auth_ollama(self) -> tuple[bool, str]:
        """Authenticate with local Ollama instance."""
        # Test connection to Ollama with a spinner
        from rich.live import Live
        from rich.spinner import Spinner
        self.console.print()
        
        success = False
        msg = ""
        with Live(
            Spinner("dots", text="[cyan]Connecting to Ollama…[/cyan]"),
            refresh_per_second=10,
            transient=True,
        ):
            success, msg = self.provider_mgr.test_provider_for_auth("ollama")
        
        if not success:
            self.console.print(Panel(
                f"[bold red]✗  Cannot connect to Ollama[/bold red]\n"
                f"[dim]{msg}[/dim]\n\n"
                f"[yellow]💡 Ollama might not be running or is on a different port.[/yellow]\n"
                f"Start Ollama with: [bold]ollama serve[/bold]",
                border_style="red", padding=(1, 2),
            ))
            if not Confirm.ask("[bold]Continue with Ollama anyway?[/bold]", default=True):
                return False, "Authentication cancelled by user."
        
        # Discover available models
        models = self.provider_mgr.list_available_models("ollama")
        if not models:
            if success:
                # Connected but no models
                return False, (
                    "✗ Ollama is running but no models found\n"
                    "[dim]Install a model with:[/dim] [bold]ollama pull llama3[/bold]"
                )
            else:
                # Not connected, using default model name
                self.config.set("ollama_model", "llama3")
                self.config.set("llm_provider", "ollama")
                return True, (
                    "✓ Ollama configured with default model 'llama3'\n"
                    "[yellow]Note: Ollama is currently unreachable.[/yellow]"
                )
        
        # Display models and let user select
        self.console.print(Panel(
            "[bold]Available Ollama models:[/bold]",
            border_style="yellow",
            padding=(0, 2)
        ))
        for i, m in enumerate(models, 1):
            self.console.print(f"  {i}. {m['id']}")
        
        try:
            choice = self.console.input("\n[bold]Select model (number, default 1):[/bold] ").strip()
            if not choice:
                choice_idx = 0
            else:
                choice_idx = int(choice) - 1
            
            if 0 <= choice_idx < len(models):
                selected = models[choice_idx]
                self.config.set("ollama_model", selected["id"])
                self.config.set("llm_provider", "ollama")
                return True, (
                    f"✓ Ollama configured successfully\n"
                    f"[green]Model: {selected['id']}[/green]"
                )
        except (ValueError, IndexError):
            self.console.print("[yellow]Invalid choice, using first available model.[/yellow]")
            selected = models[0]
            self.config.set("ollama_model", selected["id"])
            self.config.set("llm_provider", "ollama")
            return True, f"✓ Ollama configured with {selected['id']}"
        
        return False, "Model selection cancelled."
    
    def show_auth_status(self) -> None:
        """Display authentication status for all providers."""
        self.console.print("\n")
        table = Table(title="🔐 Authentication Status", box=None, header_style="bold cyan")
        table.add_column("Provider", style="cyan", width=15)
        table.add_column("Status", style="white", width=30)
        table.add_column("Model", style="green", width=30)
        
        current = self.config.get("llm_provider", "none")
        
        for provider in ["gemini", "groq", "ollama", "none"]:
            if provider == "none":
                status = "[green]✓ Ready (context only)[/green]"
                model = "N/A"
            else:
                api_key = self.config.get(f"{provider}_api_key", "")
                if api_key:
                    status = "[green]✓ Configured[/green]"
                else:
                    status = "[yellow]○ Not configured[/yellow]"
                model = self.config.get(f"{provider}_model", "default")
            
            provider_display = f"★ {provider}" if provider == current else provider
            table.add_row(provider_display, status, model)
        
        self.console.print(table)
    
    def revoke_provider_auth(self, provider: str) -> bool:
        """Revoke/remove authentication for a provider."""
        if Confirm.ask(f"\n[bold red]Remove {provider} authentication?[/bold red]", default=False):
            success = self.config.delete_secret(f"{provider}_api_key")
            if success:
                self.console.print(f"[green]✓ {provider} authentication removed[/green]")
            return success
        return False
