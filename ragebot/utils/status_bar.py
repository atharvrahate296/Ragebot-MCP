# ragebot/utils/status_bar.py
"""
StatusBar — renders a persistent provider/model/connection badge
that can be printed at the start of any AI-powered command output.
"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from typing import Optional

from ragebot.core.config import ConfigManager


def _check_provider_live(provider: str, config: ConfigManager) -> bool:
    """Quick availability check without a full test call."""
    if provider in ("gemini", "groq"):
        return bool(config.get(f"{provider}_api_key", ""))
    if provider == "ollama":
        try:
            import requests
            url = config.get("ollama_base_url", "http://localhost:11434")
            resp = requests.head(f"{url}/api/tags", timeout=1.5)
            return resp.status_code == 200
        except Exception:
            return False
    return False


def render_status_bar(config: ConfigManager, console: Console) -> None:
    """Print a compact status bar: provider · model · status."""
    provider = config.get("llm_provider", "none")
    model    = config.get(f"{provider}_model", "N/A") if provider != "none" else "N/A"
    online   = _check_provider_live(provider, config) if provider != "none" else False

    dot   = "[bold green]●[/bold green]" if online else "[bold red]●[/bold red]"
    label = f"  {dot} [cyan]{provider}[/cyan] / [dim]{model}[/dim]"

    console.print(
        Panel(label, border_style="dim", padding=(0, 2), expand=False),
        justify="right",
    )
