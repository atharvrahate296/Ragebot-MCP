# ragebot/utils/config_display.py
"""
Configuration Display - Enhanced runtime config viewing with active state.
Shows active provider, model, embeddings backend, and indexing state.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from ragebot.core.config import ConfigManager
    from ragebot.core.engine import RageBotEngine


class ConfigurationDisplay:
    """Display runtime configuration with active state."""
    
    def __init__(self, config: "ConfigManager", console: Optional[Console] = None):
        self.config = config
        self.console = console or Console()
    
    def display_runtime_config(self, engine: Optional["RageBotEngine"] = None) -> None:
        """Display complete runtime configuration with active state."""
        
        # ── Section 1: LLM Configuration ──────────────────────────────────
        llm_provider = self.config.get("llm_provider", "none")
        table_llm = Table(title="🤖 LLM Configuration", box=None, header_style="bold cyan")
        table_llm.add_column("Setting", style="cyan", width=25)
        table_llm.add_column("Value", style="green", width=40)
        
        provider_label = {
            "gemini": "Google Gemini",
            "groq": "Groq (OpenAI-compatible)",
            "ollama": "Ollama (Local)",
            "none": "None (Context Retrieval Only)",
        }.get(llm_provider, llm_provider)
        
        table_llm.add_row("Active Provider", f"[bold green]{provider_label}[/bold green]")
        
        if llm_provider != "none":
            model_key = f"{llm_provider}_model"
            model = self.config.get(model_key, "default")
            table_llm.add_row("Active Model", f"[dim]{model}[/dim]")
            
            # Check if key is configured
            key_status = self.config.get(f"{llm_provider}_api_key", "")
            if key_status:
                table_llm.add_row("API Key Status", "[green]✓ Configured[/green]")
            else:
                table_llm.add_row("API Key Status", "[yellow]✗ Not configured[/yellow]")
        
        # Max tokens
        max_tokens = self.config.get("max_answer_tokens", "1000")
        table_llm.add_row("Max Answer Tokens", max_tokens)
        
        self.console.print(table_llm)
        
        # ── Section 2: Embedding Configuration ────────────────────────────
        self.console.print()
        table_emb = Table(title="🧠 Embedding Configuration", box=None, header_style="bold cyan")
        table_emb.add_column("Setting", style="cyan", width=25)
        table_emb.add_column("Value", style="green", width=40)
        
        embedding_model = self.config.get("embedding_model", "all-MiniLM-L6-v2")
        table_emb.add_row("Embedding Model", f"[dim]{embedding_model}[/dim]")
        
        batch_size = self.config.get("embedding_batch_size", "32")
        table_emb.add_row("Batch Size", batch_size)
        
        self.console.print(table_emb)
        
        # ── Section 3: Indexing Configuration ────────────────────────────
        self.console.print()
        table_index = Table(title="📑 Indexing Configuration", box=None, header_style="bold cyan")
        table_index.add_column("Setting", style="cyan", width=25)
        table_index.add_column("Value", style="green", width=40)
        
        chunk_size = self.config.get("chunk_size", "512")
        chunk_overlap = self.config.get("chunk_overlap", "64")
        table_index.add_row("Chunk Size", f"{chunk_size} tokens")
        table_index.add_row("Chunk Overlap", f"{chunk_overlap} tokens")
        
        top_k = self.config.get("default_top_k", "5")
        table_index.add_row("Default Top-K", top_k)
        
        max_file_size = self.config.get("max_file_size_kb", "500")
        table_index.add_row("Max File Size", f"{max_file_size} KB")
        
        max_chunks = self.config.get("max_chunks_per_file", "20")
        table_index.add_row("Max Chunks/File", max_chunks)
        
        index_depth = self.config.get("index_depth", "10")
        table_index.add_row("Index Depth", index_depth)
        
        cache_enabled = self.config.get_bool("context_cache_enabled", True)
        cache_status = "[green]✓ Enabled[/green]" if cache_enabled else "[yellow]✗ Disabled[/yellow]"
        table_index.add_row("Context Cache", cache_status)
        
        self.console.print(table_index)
        
        # ── Section 4: Project State (if engine provided) ──────────────────
        if engine and (engine.project_path / ".ragebot" / "ragebot.db").exists():
            self.console.print()
            status = engine.get_status()
            table_proj = Table(title="📊 Project Index State", box=None, header_style="bold cyan")
            table_proj.add_column("Setting", style="cyan", width=25)
            table_proj.add_column("Value", style="green", width=40)
            
            table_proj.add_row("Indexed Files", str(status.get("indexed_files", 0)))
            table_proj.add_row("Modified Since Save", str(status.get("modified_since", 0)))
            table_proj.add_row("Snapshots Saved", str(status.get("snapshot_count", 0)))
            table_proj.add_row("Database Size", str(status.get("db_size", "N/A")))
            table_proj.add_row("Last Saved", str(status.get("last_saved", "Never")))
            
            self.console.print(table_proj)
        
        # ── Section 5: Ignore Patterns ───────────────────────────────────
        self.console.print()
        table_ignore = Table(title="🚫 Ignore Patterns", box=None, header_style="bold cyan")
        table_ignore.add_column("Pattern", style="dim", width=80)
        
        patterns = self.config.get_ignore_patterns()
        for pattern in patterns[:15]:  # Show first 15
            table_ignore.add_row(pattern)
        
        if len(patterns) > 15:
            table_ignore.add_row(f"... and {len(patterns) - 15} more")
        
        self.console.print(table_ignore)
    
    def display_quick_config(self) -> None:
        """Display quick summary of active configuration."""
        llm_provider = self.config.get("llm_provider", "none")
        llm_model = self.config.get(f"{llm_provider}_model", "default") if llm_provider != "none" else "N/A"
        embedding_model = self.config.get("embedding_model", "all-MiniLM-L6-v2")
        
        self.console.print(Panel(
            f"[cyan]LLM Provider:[/cyan]     {llm_provider}\n"
            f"[cyan]LLM Model:[/cyan]        {llm_model}\n"
            f"[cyan]Embedding Model:[/cyan]  {embedding_model}",
            title="[bold]⚙️  Configuration[/bold]",
            border_style="cyan",
            padding=(0, 2)
        ))
    
    def display_env_overrides(self) -> None:
        """Show environment variables that override config."""
        import os
        from ragebot.core.config import _ENV_MAP
        
        overrides = []
        for env_key, cfg_key in _ENV_MAP.items():
            if env_key in os.environ:
                value = os.environ[env_key]
                overrides.append((env_key, value))
        
        if not overrides:
            self.console.print("[dim]No environment variable overrides active[/dim]")
            return
        
        table = Table(title="🌍 Environment Variable Overrides", box=None, header_style="bold yellow")
        table.add_column("Variable", style="yellow", width=30)
        table.add_column("Value", style="green", width=40)
        
        for env_key, value in overrides:
            table.add_row(env_key, value)
        
        self.console.print(table)
    
    def compare_config(self, other_config: "ConfigManager") -> None:
        """Compare two configurations side by side."""
        table = Table(title="🔀 Configuration Comparison", box=None, header_style="bold cyan")
        table.add_column("Setting", style="cyan", width=25)
        table.add_column("Current", style="green", width=35)
        table.add_column("Other", style="yellow", width=35)
        
        # Key settings to compare
        keys_to_compare = [
            "llm_provider",
            "embedding_model",
            "chunk_size",
            "default_top_k",
            "max_file_size_kb",
            "context_cache_enabled",
        ]
        
        for key in keys_to_compare:
            current_val = str(self.config.get(key, "N/A"))
            other_val = str(other_config.get(key, "N/A"))
            
            # Highlight differences
            if current_val != other_val:
                current_val = f"[bold green]{current_val}[/bold green]"
                other_val = f"[bold yellow]{other_val}[/bold yellow]"
            
            table.add_row(key, current_val, other_val)
        
        self.console.print(table)
    
    def export_config_snapshot(self, output_path: Path) -> bool:
        """Export current configuration to a file."""
        import json
        try:
            config_data = {
                "llm_provider": self.config.get("llm_provider", "none"),
                "llm_model": self.config.get(
                    f"{self.config.get('llm_provider', 'none')}_model",
                    "default"
                ),
                "embedding_model": self.config.get("embedding_model", "all-MiniLM-L6-v2"),
                "chunk_size": int(self.config.get("chunk_size", "512")),
                "default_top_k": int(self.config.get("default_top_k", "5")),
                "max_file_size_kb": int(self.config.get("max_file_size_kb", "500")),
                "context_cache_enabled": self.config.get_bool("context_cache_enabled", True),
                "ignore_patterns": self.config.get_ignore_patterns(),
            }
            output_path.write_text(json.dumps(config_data, indent=2))
            return True
        except Exception:
            return False
