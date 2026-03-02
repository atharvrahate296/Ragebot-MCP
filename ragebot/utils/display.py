"""
Display - Rich terminal output helpers.
"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


class Display:
    def __init__(self):
        self.console = Console()

    def success(self, message: str):
        self.console.print(f"[bold green]✓[/bold green] {message}")

    def error(self, message: str):
        self.console.print(f"[bold red]✗[/bold red] {message}")

    def info(self, message: str):
        self.console.print(f"[bold blue]ℹ[/bold blue] {message}")

    def warning(self, message: str):
        self.console.print(f"[bold yellow]⚠[/bold yellow] {message}")

    def banner(self):
        self.console.print(Panel(
            "[bold cyan]██████╗  █████╗  ██████╗ ███████╗██████╗  ██████╗ ████████╗\n"
            "[bold cyan]██╔══██╗██╔══██╗██╔════╝ ██╔════╝██╔══██╗██╔═══██╗╚══██╔══╝\n"
            "[bold cyan]██████╔╝███████║██║  ███╗█████╗  ██████╔╝██║   ██║   ██║   \n"
            "[bold cyan]██╔══██╗██╔══██║██║   ██║██╔══╝  ██╔══██╗██║   ██║   ██║   \n"
            "[bold cyan]██║  ██║██║  ██║╚██████╔╝███████╗██████╔╝╚██████╔╝   ██║   \n"
            "[bold cyan]╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═════╝  ╚═════╝    ╚═╝   \n\n"
            "[dim]Intelligent Project Context Engine  •  v1.0.0[/dim]",
            border_style="cyan",
            subtitle="[dim]github.com/ragebot/mcp[/dim]",
        ))
