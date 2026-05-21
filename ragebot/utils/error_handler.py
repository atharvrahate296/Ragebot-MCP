# ragebot/utils/error_handler.py
"""
Error Handler - Advanced error handling with recovery suggestions.
Provides actionable feedback for provider failures, indexing issues, and auth problems.
"""
from __future__ import annotations

from typing import Optional
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown


class ErrorSeverity(Enum):
    """Error severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories."""
    PROVIDER_FAILURE = "provider_failure"
    AUTHENTICATION = "authentication"
    INDEXING = "indexing"
    SNAPSHOT = "snapshot"
    RATE_LIMIT = "rate_limit"
    FILE_NOT_FOUND = "file_not_found"
    CONFIG = "config"
    NETWORK = "network"
    UNKNOWN = "unknown"


class RageBotError(Exception):
    """Base exception for RageBot errors."""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        recovery_steps: Optional[list[str]] = None,
        context: Optional[dict] = None,
    ):
        self.message = message
        self.category = category
        self.severity = severity
        self.recovery_steps = recovery_steps or []
        self.context = context or {}
        super().__init__(self.message)


class ErrorHandler:
    """Handle and display errors with recovery suggestions."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def handle_error(self, error: Exception, context: Optional[str] = None) -> None:
        """
        Handle an exception and display it with recovery suggestions.
        
        Args:
            error: The exception to handle
            context: Optional context string describing what was being done
        """
        if isinstance(error, RageBotError):
            self._handle_ragebot_error(error, context)
        else:
            self._handle_generic_error(error, context)
    
    def _handle_ragebot_error(self, error: RageBotError, context: Optional[str] = None) -> None:
        """Handle a RageBotError with full context and recovery steps."""
        
        # Determine border color by severity
        color_map = {
            ErrorSeverity.INFO: "blue",
            ErrorSeverity.WARNING: "yellow",
            ErrorSeverity.ERROR: "red",
            ErrorSeverity.CRITICAL: "red",
        }
        border = color_map.get(error.severity, "red")
        
        # Build the error display
        lines = [f"[bold]{error.message}[/bold]"]
        
        if context:
            lines.append(f"\n[dim]Context: {context}[/dim]")
        
        # Add category info
        category_label = error.category.value.replace("_", " ").title()
        lines.append(f"\n[cyan]Category:[/cyan] {category_label}")
        
        # Add recovery steps
        if error.recovery_steps:
            lines.append(f"\n[bold yellow]Recovery Steps:[/bold yellow]")
            for i, step in enumerate(error.recovery_steps, 1):
                lines.append(f"  {i}. {step}")
        
        # Add additional context if provided
        if error.context:
            lines.append(f"\n[dim]Additional Details:[/dim]")
            for key, value in error.context.items():
                lines.append(f"  {key}: {value}")
        
        # Display the error panel
        self.console.print(Panel(
            "\n".join(lines),
            title=f"[bold]{error.severity.value.upper()}[/bold]",
            border_style=border,
            padding=(1, 2),
        ))
    
    def _handle_generic_error(self, error: Exception, context: Optional[str] = None) -> None:
        """Handle a generic exception."""
        error_msg = str(error)
        error_type = type(error).__name__
        
        lines = [
            f"[bold {error_type}][/bold]\n",
            f"{error_msg}",
        ]
        
        if context:
            lines.append(f"\n[dim]Context: {context}[/dim]")
        
        self.console.print(Panel(
            "\n".join(lines),
            title="[bold]ERROR[/bold]",
            border_style="red",
            padding=(1, 2),
        ))
    
    def raise_provider_error(
        self,
        provider: str,
        error_msg: str,
        recovery_steps: Optional[list[str]] = None,
    ) -> None:
        """Raise a provider failure error with recovery steps."""
        if recovery_steps is None:
            recovery_steps = [
                f"Check your {provider} API key is valid: rage auth status",
                f"Test provider connection: rage model",
                "Try switching to a different provider: rage auth login",
            ]
        
        raise RageBotError(
            f"{provider} Provider Error: {error_msg}",
            category=ErrorCategory.PROVIDER_FAILURE,
            severity=ErrorSeverity.ERROR,
            recovery_steps=recovery_steps,
            context={"provider": provider},
        )
    
    def raise_auth_error(
        self,
        provider: str,
        reason: str,
    ) -> None:
        """Raise an authentication error."""
        recovery_steps = [
            f"Login to {provider}: rage auth login {provider}",
            "View auth status: rage auth status",
            "Get API key from the provider's website",
        ]
        
        raise RageBotError(
            f"Authentication Error: {reason}",
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.ERROR,
            recovery_steps=recovery_steps,
            context={"provider": provider},
        )
    
    def raise_indexing_error(
        self,
        file_path: str,
        error_msg: str,
    ) -> None:
        """Raise an indexing error."""
        recovery_steps = [
            f"Re-run indexing: rage save --full",
            f"Check file permissions: {file_path}",
            "Verify file is not corrupted",
            f"Exclude the file from indexing in config",
        ]
        
        raise RageBotError(
            f"Indexing Error: {error_msg}",
            category=ErrorCategory.INDEXING,
            severity=ErrorSeverity.WARNING,
            recovery_steps=recovery_steps,
            context={"file_path": file_path},
        )
    
    def raise_rate_limit_error(
        self,
        provider: str,
        retry_after: Optional[int] = None,
    ) -> None:
        """Raise a rate limit error."""
        retry_msg = f" (retry in {retry_after}s)" if retry_after else ""
        recovery_steps = [
            f"Wait and retry in a few moments{retry_msg}",
            f"Upgrade your {provider} API quota",
            "Switch to a different provider",
            "Reduce request frequency or batch size",
        ]
        
        raise RageBotError(
            f"{provider} Rate Limit Exceeded",
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.WARNING,
            recovery_steps=recovery_steps,
            context={"provider": provider, "retry_after": retry_after},
        )
    
    def raise_snapshot_error(
        self,
        operation: str,
        snapshot_name: str,
        error_msg: str,
    ) -> None:
        """Raise a snapshot operation error."""
        recovery_steps = [
            f"Check snapshot exists: rage snapshot list",
            "Verify disk space available",
            "Check file permissions in .ragebot/snapshots",
            "Try creating a new snapshot",
        ]
        
        raise RageBotError(
            f"Snapshot {operation} Error: {error_msg}",
            category=ErrorCategory.SNAPSHOT,
            severity=ErrorSeverity.ERROR,
            recovery_steps=recovery_steps,
            context={"operation": operation, "snapshot_name": snapshot_name},
        )
    
    def raise_network_error(
        self,
        endpoint: str,
        error_msg: str,
    ) -> None:
        """Raise a network error."""
        recovery_steps = [
            "Check your internet connection",
            f"Verify endpoint is reachable: {endpoint}",
            "Check firewall/proxy settings",
            "Try again in a few moments",
        ]
        
        raise RageBotError(
            f"Network Error: {error_msg}",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR,
            recovery_steps=recovery_steps,
            context={"endpoint": endpoint},
        )
    
    def display_warning(self, message: str, title: str = "⚠️  Warning") -> None:
        """Display a warning message."""
        self.console.print(Panel(
            message,
            title=f"[bold yellow]{title}[/bold yellow]",
            border_style="yellow",
            padding=(0, 2),
        ))
    
    def display_info(self, message: str, title: str = "ℹ️  Info") -> None:
        """Display an info message."""
        self.console.print(Panel(
            message,
            title=f"[bold blue]{title}[/bold blue]",
            border_style="blue",
            padding=(0, 2),
        ))
    
    def display_success(self, message: str, title: str = "✓ Success") -> None:
        """Display a success message."""
        self.console.print(Panel(
            message,
            title=f"[bold green]{title}[/bold green]",
            border_style="green",
            padding=(0, 2),
        ))


# Global error handler instance
_global_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get the global error handler (lazy init)."""
    global _global_handler
    if _global_handler is None:
        _global_handler = ErrorHandler()
    return _global_handler


def handle_error(error: Exception, context: Optional[str] = None) -> None:
    """Convenience function to handle an error globally."""
    get_error_handler().handle_error(error, context)
