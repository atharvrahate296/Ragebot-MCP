"""
UI Helpers - Status displays, colored output, and interactive menu utilities.

Provides:
- Provider and model status display with color coding
- Loading indicators and progress messages
- Interactive selection helpers
- Error and success message formatting
"""
from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from typing import Optional


class ProviderStatusDisplay:
    """Display provider connectivity and configuration status."""
    
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
    
    def show_status(self, provider: str, is_available: bool, model: str = "") -> None:
        """
        Display a single provider's status with color coding.
        
        Colors:
        - Green: Online and configured
        - Red: Offline or not configured
        - Yellow: Available but missing API key
        """
        if is_available:
            status_text = "[bold green]●[/bold green] Online"
            status_color = "green"
        else:
            status_text = "[bold red]●[/bold red] Offline"
            status_color = "red"
        
        model_info = f" → {model}" if model else ""
        self.console.print(f"  {provider.title():<12} {status_text}{model_info}")
    
    def show_all_providers(
        self,
        providers: dict[str, dict],  # {"gemini": {"available": True, "model": "..."}, ...}
        active: str = ""
    ) -> None:
        """
        Display all providers in a formatted table.
        
        Args:
            providers: Dict mapping provider name to {available, model, status}
            active: Name of the currently active provider
        """
        table = Table(title="🔌 LLM Providers", box=None, header_style="bold cyan")
        table.add_column("Provider", style="cyan", min_width=15)
        table.add_column("Status", style="white", min_width=20)
        table.add_column("Model", style="dim", min_width=30)
        
        for name, info in providers.items():
            is_available = info.get("available", False)
            model = info.get("model", "N/A")
            status_key = info.get("status", "not_configured")
            
            # Status icon and color
            if is_available:
                status_icon = "[bold green]✓[/bold green]"
                status_label = "Online"
                status_style = "green"
            elif status_key == "missing_key":
                status_icon = "[bold yellow]⚠[/bold yellow]"
                status_label = "Missing API Key"
                status_style = "yellow"
            elif status_key == "offline":
                status_icon = "[bold red]✗[/bold red]"
                status_label = "Offline"
                status_style = "red"
            else:
                status_icon = "[bold yellow]◎[/bold yellow]"
                status_label = "Not Configured"
                status_style = "yellow"
            
            # Mark active provider
            name_display = f"{name.title()}"
            if name == active:
                name_display = f"[bold cyan]★ {name_display}[/bold cyan]"
            
            table.add_row(
                name_display,
                f"{status_icon} {status_label}",
                model
            )
        
        self.console.print(table)


class LoadingIndicator:
    """Clean loading messages without raw library logs."""
    
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
    
    def show_loading(self, message: str) -> None:
        """Display a friendly loading message."""
        self.console.print(f"[cyan]⟳[/cyan] {message}", end=" ", style="dim")
    
    def show_complete(self, message: str = "Done") -> None:
        """Mark loading as complete."""
        self.console.print(f"[bold green]✓[/bold green] {message}")
    
    def show_error(self, message: str) -> None:
        """Show loading error."""
        self.console.print(f"[bold red]✗[/bold red] {message}")


class ModelSelector:
    """Interactive model selection with proper display."""
    
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
    
    def display_models(
        self,
        models: list[dict],
        current_model: str = "",
        title: str = "Available Models"
    ) -> None:
        """
        Display available models in a formatted table.
        
        Args:
            models: List of {id, name, description} dicts
            current_model: Currently selected model ID
            title: Table title
        """
        table = Table(title=f"📜 {title}", box=None, header_style="bold cyan")
        table.add_column("Name", style="bold yellow", min_width=25)
        table.add_column("ID", style="dim", min_width=35)
        table.add_column("Description", style="white")
        
        for model in models:
            name = model.get("name", "Unknown")
            model_id = model.get("id", "unknown")
            desc = model.get("description", "")
            
            # Mark current model
            if model_id == current_model:
                name = f"[bold green]● {name}[/bold green]"
            else:
                name = f"  {name}"
            
            table.add_row(name, f"[dim]{model_id}[/dim]", desc[:50])
        
        self.console.print(table)


def show_provider_health_check(console: Console, provider_name: str, is_online: bool) -> None:
    """
    Show a health check result for a provider.
    
    Args:
        console: Rich Console instance
        provider_name: Name of the provider
        is_online: Whether provider is responding
    """
    if is_online:
        console.print(
            Panel(
                f"[bold green]✓ {provider_name} is online and ready[/bold green]",
                border_style="green",
                padding=(0, 2)
            )
        )
    else:
        console.print(
            Panel(
                f"[bold red]✗ {provider_name} is not responding[/bold red]\n"
                f"[dim]Check your API key and network connection[/dim]",
                border_style="red",
                padding=(0, 2)
            )
        )


def show_friendly_error(console: Console, title: str, message: str, suggestion: str = "") -> None:
    """
    Display a user-friendly error message.
    
    Args:
        console: Rich Console instance
        title: Error title
        message: Error explanation
        suggestion: Suggested action to fix
    """
    error_text = f"[bold red]{title}[/bold red]\n\n[dim]{message}"
    if suggestion:
        error_text += f"\n\n[yellow]💡 {suggestion}[/yellow]"
    
    console.print(Panel(error_text, border_style="red", padding=(1, 2)))


def show_success_badge(console: Console, message: str) -> None:
    """Display a success message with badge."""
    console.print(f"[bold green]✓[/bold green] {message}")


def show_warning_badge(console: Console, message: str) -> None:
    """Display a warning message with badge."""
    console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def show_info_badge(console: Console, message: str) -> None:
    """Display an info message with badge."""
    console.print(f"[bold blue]ℹ[/bold blue] {message}")


def show_bottom_error(console: Console, title: str, detail: str) -> None:
    """
    Print a compact error notification suitable for bottom-of-screen display.
    Used for rate-limit hits, background re-index failures, etc.
    """
    console.print()
    console.print(
        Panel(
            f"[bold red]{title}[/bold red]  [dim]{detail}[/dim]",
            border_style="red",
            padding=(0, 2),
            expand=False,
        ),
        justify="right",
    )


def show_bottom_warning(console: Console, title: str, detail: str) -> None:
    """Compact warning notification for bottom-of-screen display."""
    console.print(
        Panel(
            f"[bold yellow]{title}[/bold yellow]  [dim]{detail}[/dim]",
            border_style="yellow",
            padding=(0, 2),
            expand=False,
        ),
        justify="right",
    )
