# ragebot/core/commands.py
"""
Plain-Python command implementations.
No Typer dependency — callable from REPL, CLI, MCP, or tests.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from ragebot.core.config import ConfigManager
from ragebot.core.engine import RageBotEngine
from ragebot.utils.error_handler import RageBotError, ErrorHandler, ErrorCategory
from ragebot.utils.ui_helpers import (
    show_friendly_error, show_success_badge,
    show_warning_badge, show_info_badge,
)

console = Console()
_err = ErrorHandler(console)


def _engine(path: str = ".") -> RageBotEngine:
    return RageBotEngine(
        project_path=Path(path).resolve(),
        config=ConfigManager(),
    )


# ── init ─────────────────────────────────────────────────────────────────────

def do_init(path: str = ".", force: bool = False) -> None:
    """Initialize RageBot for a project directory."""
    from rich.progress import Progress, SpinnerColumn, TextColumn
    try:
        eng = _engine(path)
        with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}"),
                      transient=True) as p:
            task = p.add_task("Initialising…", total=None)
            result = eng.initialize(force=force)
            p.update(task, description=f"Initialised {result['file_count']} files")
        show_success_badge(console, f"Initialised at [bold]{result['path']}[/bold]")
        show_info_badge(console, f"[bold]{result['file_count']}[/bold] indexable files found.")
        show_info_badge(console, "Run [bold cyan]save[/bold cyan] to index the project.")
    except RageBotError as e:
        _err.handle_error(e)
    except Exception as e:
        show_friendly_error(console, "Initialization Error", str(e))


# ── save ─────────────────────────────────────────────────────────────────────

def do_save(path: str = ".", incremental: bool = True,
            snapshot_name: Optional[str] = None) -> None:
    """Index project and save snapshot."""
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.prompt import Prompt, Confirm
    try:
        eng = _engine(path)
        if not (eng.project_path / ".ragebot" / "ragebot.db").exists():
            show_info_badge(console, "Project not initialized — running init first…")
            eng.initialize()

        if not snapshot_name:
            default_name = f"snap_{int(time.time())}"
            snapshot_name = Prompt.ask(
                "[bold]Snapshot name[/bold] [dim](Enter for auto)[/dim]",
                default=default_name,
            ).strip() or default_name

        # ── Check LLM availability; offer index-only fallback for Ollama ──
        from ragebot.llm.factory import get_provider
        _provider_ok = True
        try:
            _prov = get_provider(ConfigManager())
            _provider_ok = _prov.is_available()
        except Exception:
            _provider_ok = False

        if not _provider_ok:
            _pname = ConfigManager().get("llm_provider", "none")
            if _pname not in ("none", ""):
                show_warning_badge(
                    console,
                    f"[bold yellow]{_pname.title()}[/bold yellow] provider is not reachable. "
                    "Indexing will proceed without LLM features."
                )

        # ── Step 1: Scan ──────────────────────────────────────────────────
        with Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[bold cyan]{task.description}"),
            transient=True,
            console=console,
        ) as p:
            t1 = p.add_task("[1/2] Scanning files…", total=None)
            from ragebot.core.scanner import DirectoryScanner
            scanner = DirectoryScanner(eng.project_path, eng.config)
            all_files = scanner.scan()
            p.update(t1, description=f"[1/2] Scanning files… [dim]{len(all_files)} found[/dim]")

        # ── Step 2: Embed & index ─────────────────────────────────────────
        with Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            transient=True,
            console=console,
        ) as p:
            t2 = p.add_task(f"[2/2] Embedding {len(all_files)} files…", total=len(all_files))

            result = eng.save(incremental=incremental, snapshot_name=snapshot_name)
            p.update(t2, completed=len(all_files))

        t = Table(title="📊 Indexing Summary", box=None, header_style="bold cyan")
        t.add_column("Metric", style="cyan", min_width=20)
        t.add_column("Value",  style="green")
        t.add_row("Snapshot Name",    result["snapshot_name"])
        t.add_row("Files Indexed",    str(result["indexed"]))
        t.add_row("Files Skipped",    str(result["skipped"]))
        t.add_row("Tokens Estimated", str(result["token_estimate"]))
        t.add_row("Timestamp",        time.strftime("%Y-%m-%d %H:%M:%S"))
        console.print(t)
    except RageBotError as e:
        _err.handle_error(e)
    except Exception as e:
        show_friendly_error(console, "Save Error", str(e))


# ── ask ──────────────────────────────────────────────────────────────────────

def do_ask(query: str, path: str = ".", mode: str = "smart",
           top_k: int = 5, show_files: bool = True,
           export: Optional[str] = None) -> None:
    """Single-turn AI question."""
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from ragebot.utils.status_bar import render_status_bar
    try:
        render_status_bar(ConfigManager(), console)
        eng = _engine(path)
        with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}"),
                      transient=True) as p:
            p.add_task(f"Thinking about: {query!r}…", total=None)
            result = eng.ask(query=query, mode=mode, top_k=top_k)

        console.print(Panel(f"[bold yellow]{query}[/bold yellow]",
                            title="❓ Query", border_style="blue"))
        answer = result.get("answer", "")
        if answer:
            console.print(Panel(Markdown(answer), title="💡 Answer", border_style="green"))
        if show_files and result.get("sources"):
            t = Table(title="📁 Sources", box=None, header_style="bold cyan")
            t.add_column("File",  style="cyan")
            t.add_column("Score", style="yellow")
            t.add_column("Type",  style="magenta")
            for s in result["sources"]:
                t.add_row(s["file"], f"{s['score']:.3f}", s["type"])
            console.print(t)
        if export:
            Path(export).write_text(json.dumps(result, indent=2))
            show_success_badge(console, f"Saved to [bold]{export}[/bold]")
    except RageBotError as e:
        _err.handle_error(e)
        if e.category == ErrorCategory.RATE_LIMIT:
            _prompt_provider_switch()
    except Exception as e:
        show_friendly_error(console, "Ask Error", str(e))


# ── explain ──────────────────────────────────────────────────────────────────

def do_explain(file_path: str, symbol: Optional[str] = None,
               path: str = ".") -> None:
    """Explain a file or symbol."""
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from ragebot.utils.status_bar import render_status_bar
    try:
        render_status_bar(ConfigManager(), console)
        eng = _engine(path)
        resolved = _resolve_file_path(eng, file_path)
        if not resolved:
            show_friendly_error(
                console, "File Not Found",
                f"'{file_path}' is not indexed.",
                "Run 'save' to index your project first.",
            )
            return
        with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}"),
                      transient=True) as p:
            p.add_task(f"Explaining {resolved}…", total=None)
            result = eng.explain(resolved, symbol)
        if "error" in result:
            show_friendly_error(console, "Explain Error", result["error"])
            return
        console.print(Panel(Markdown(result.get("explanation", "")),
                            title="💡 Explanation", border_style="green"))
    except RageBotError as e:
        _err.handle_error(e)
        if e.category == ErrorCategory.RATE_LIMIT:
            _prompt_provider_switch()
    except Exception as e:
        show_friendly_error(console, "Explain Error", str(e))


# ── docs ─────────────────────────────────────────────────────────────────────

def do_docs(file_path: str, path: str = ".",
            output: Optional[str] = None) -> None:
    """Generate Markdown documentation for a file."""
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from ragebot.utils.status_bar import render_status_bar
    try:
        render_status_bar(ConfigManager(), console)
        eng = _engine(path)
        with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}"),
                      transient=True) as p:
            p.add_task("Generating docs…", total=None)
            docs = eng.generate_docs(file_path)
        console.print(Panel(Markdown(docs), border_style="cyan"))
        if output:
            Path(output).write_text(docs)
            show_success_badge(console, f"Saved to [bold]{output}[/bold]")
    except RageBotError as e:
        _err.handle_error(e)
    except Exception as e:
        show_friendly_error(console, "Docs Error", str(e))


# ── test ─────────────────────────────────────────────────────────────────────

def do_test(file_path: str, path: str = ".",
            output: Optional[str] = None) -> None:
    """Generate pytest tests for a file."""
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from ragebot.utils.status_bar import render_status_bar
    try:
        render_status_bar(ConfigManager(), console)
        eng = _engine(path)
        with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}"),
                      transient=True) as p:
            p.add_task("Generating tests…", total=None)
            tests = eng.generate_tests(file_path)
        console.print(Panel(Syntax(tests, "python"), border_style="cyan"))
        if output:
            Path(output).write_text(tests)
            show_success_badge(console, f"Saved to [bold]{output}[/bold]")
    except RageBotError as e:
        _err.handle_error(e)
    except Exception as e:
        show_friendly_error(console, "Test Error", str(e))


# ── search ───────────────────────────────────────────────────────────────────

def do_search(query: str, path: str = ".",
              search_type: str = "semantic", top_k: int = 10) -> None:
    """Semantic / keyword / hybrid search."""
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from ragebot.utils.search_formatter import SearchResultFormatter
    try:
        eng = _engine(path)
        formatter = SearchResultFormatter(console)
        with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}"),
                      transient=True) as p:
            p.add_task(f"Searching: {query!r}…", total=None)
            results = eng.search(query=query, search_type=search_type, top_k=top_k)
        if not results:
            show_info_badge(console, "No results found.")
            return
        formatter.format_results(results, query=query)
    except RageBotError as e:
        _err.handle_error(e)
    except Exception as e:
        show_friendly_error(console, "Search Error", str(e))


# ── status ───────────────────────────────────────────────────────────────────

def do_status(path: str = ".") -> None:
    """Show index status with live provider ping indicators."""
    from rich.live import Live
    from rich.spinner import Spinner
    try:
        eng = _engine(path)
        if not (eng.rage_dir / "ragebot.db").exists():
            show_warning_badge(console, f"Project at {path} is not initialized.")
            return
        s = eng.get_status()

        # ── Live-ping the provider ────────────────────────────────────────
        provider_name = s.get("llm_provider", "none")
        llm_ok = False
        ping_detail = ""
        with Live(
            Spinner("dots", text=f"[cyan]Pinging {provider_name}…[/cyan]"),
            refresh_per_second=10,
            transient=True,
            console=console,
        ):
            try:
                from ragebot.llm.factory import get_provider as _gp
                _prov = _gp(ConfigManager())
                llm_ok = _prov.is_available()
                ping_detail = "reachable" if llm_ok else "not reachable"
            except Exception as _pe:
                llm_ok = False
                ping_detail = str(_pe)[:60]

        if llm_ok:
            llm_status = f"[bold green]✓ Connected[/bold green]  [dim]{ping_detail}[/dim]"
        else:
            llm_status = (
                f"[bold red]✗ Not reachable[/bold red]  [dim]{ping_detail}[/dim]\n"
                f"  [yellow]💡 rage auth login {provider_name}[/yellow]"
            )

        # ── Modified-files indicator ──────────────────────────────────────
        modified = s.get("modified_since", 0)
        modified_str = (
            f"[yellow]{modified} file(s) changed since last save[/yellow]"
            if modified > 0
            else "[green]Up to date[/green]"
        )

        console.print(Panel(
            f"[cyan]Project:[/cyan]          {s.get('project_path')}\n"
            f"[cyan]Indexed Files:[/cyan]    {s.get('indexed_files')}  [dim]({s.get('db_size', 'N/A')})[/dim]\n"
            f"[cyan]Last Saved:[/cyan]       {s.get('last_saved', 'Never')}\n"
            f"[cyan]Modified Since:[/cyan]   {modified_str}\n"
            f"[cyan]Snapshots:[/cyan]        {s.get('snapshot_count', 0)}\n"
            f"[cyan]Embedding Model:[/cyan]  {s.get('embedding_model', 'N/A')}\n"
            f"[cyan]LLM Provider:[/cyan]     [bold]{provider_name}[/bold]\n"
            f"[cyan]LLM Status:[/cyan]       {llm_status}",
            title="📡 RageBot Status", border_style="blue",
        ))
    except RageBotError as e:
        _err.handle_error(e)
    except Exception as e:
        show_friendly_error(console, "Status Error", str(e))


# ── context ──────────────────────────────────────────────────────────────────

def do_context(path: str = ".", tree: bool = False) -> None:
    """Show project overview / file tree."""
    try:
        eng = _engine(path)
        if tree:
            console.print(eng.get_file_tree()["tree"])
        else:
            stats = eng.get_project_overview()
            for k, v in stats.items():
                console.print(f"{k}: {v}")
    except RageBotError as e:
        _err.handle_error(e)
    except Exception as e:
        show_friendly_error(console, "Context Error", str(e))


# ── snapshot ─────────────────────────────────────────────────────────────────

def do_snapshot(action: str = "list", name: Optional[str] = None,
                path: str = ".") -> None:
    """Manage snapshots: list | restore | delete."""
    from rich.prompt import Confirm
    try:
        eng = _engine(path)
        from ragebot.storage.snapshot import SnapshotManager
        sm = SnapshotManager(eng.rage_dir / "snapshots")
        action = action.lower()

        if action == "list":
            snaps = sm.list_snapshots()
            if not snaps:
                show_info_badge(console, "No snapshots found.")
                return
            t = Table(title="📸 Snapshots", box=None, header_style="bold cyan")
            t.add_column("",       style="yellow", width=3)
            t.add_column("Name",   style="cyan")
            t.add_column("Created",style="yellow")
            t.add_column("Files",  style="green")
            t.add_column("Size",   style="dim")
            for s in snaps:
                marker = "★" if s.get("active") else " "
                t.add_row(marker, s["name"], s["created"], str(s["files"]), s["size"])
            console.print(t)
            console.print("[dim]★ = currently active snapshot[/dim]")

        elif action == "restore":
            if not name:
                show_friendly_error(console, "Argument Error",
                                    "Snapshot name required for restore.")
                return
            sm.restore(name)
            show_success_badge(console, f"Restored snapshot: [bold]{name}[/bold]")

        elif action == "delete":
            if not name:
                show_friendly_error(console, "Argument Error",
                                    "Snapshot name required for delete.")
                return
            if Confirm.ask(f"Delete snapshot [bold]{name}[/bold]?", default=False):
                sm.delete(name)
                show_success_badge(console, f"Deleted snapshot: [bold]{name}[/bold]")
        else:
            show_friendly_error(console, "Unknown Action", "Use: list, restore, delete")
    except RageBotError as e:
        _err.handle_error(e)
    except Exception as e:
        show_friendly_error(console, "Snapshot Error", str(e))


# ── helpers ──────────────────────────────────────────────────────────────────

def _resolve_file_path(eng: RageBotEngine, file_path: str) -> Optional[str]:
    """Resolve a partial/relative path against the indexed files."""
    import os
    if eng.db.get_file(file_path):
        return file_path
    normalized = file_path.replace("\\", "/")
    all_files = eng.db.get_all_files()
    for f in all_files:
        fp = f["file_path"].replace("\\", "/")
        if fp == normalized or fp.endswith("/" + normalized) or fp.endswith(normalized):
            return f["file_path"]
    basename = os.path.basename(file_path)
    for f in all_files:
        if os.path.basename(f["file_path"]) == basename:
            return f["file_path"]
    return None


def _prompt_provider_switch() -> None:
    """Prompt user to switch provider after a rate-limit error."""
    try:
        import questionary
        switch = questionary.confirm(
            "Switch to a different provider now?",
            default=False,
        ).ask()
        if switch:
            from ragebot.cli import _do_switch_interactive
            _do_switch_interactive()
    except Exception:
        pass  # questionary may not be installed or user cancelled
