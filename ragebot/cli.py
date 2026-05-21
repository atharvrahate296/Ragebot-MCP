"""
RageBot MCP — CLI Entry Point (Updated)
════════════════════════════════════════
Modern interactive CLI with:
✓ Proper command structure (ragebot → REPL, rage <cmd> → standard)
✓ Interactive menus (arrow keys, mouse support via questionary)
✓ Live provider/model status
✓ Ollama support with auto-detection
✓ Friendly error messages
✓ Snapshot naming prompts
✓ Masked API key input
✓ Provider isolation
"""
from __future__ import annotations

import json
import uuid
import getpass
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table

from ragebot.core.config import ConfigManager
from ragebot.core.engine import RageBotEngine
from ragebot.utils.display import Display
from ragebot.utils.logging_config import suppress_noisy_logs
from ragebot.utils.ui_helpers import (
    ProviderStatusDisplay, LoadingIndicator, show_friendly_error,
    show_success_badge, show_warning_badge, show_info_badge
)
import questionary




# Suppress noisy HuggingFace logs on startup
suppress_noisy_logs()

# ── App & globals ─────────────────────────────────────────────────────────────
app = typer.Typer(
    name="rage",
    help="🤖 [bold cyan]RageBot[/bold cyan] — Intelligent Project Context Engine\n\n[dim]Scan projects, index code, ask AI questions, generate docs & tests.[/dim]",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=False,
)
console = Console()
display = Display()

PROVIDERS = ["gemini", "groq", "ollama"]

_PROVIDER_META = {
    "gemini": {"icon": "✦", "color": "blue",  "label": "Google Gemini", "desc": "Google's multimodal AI"},
    "groq":   {"icon": "⚡", "color": "green", "label": "Groq",          "desc": "Ultra-fast LLM inference"},
    "ollama": {"icon": "🦙", "color": "yellow", "label": "Ollama",       "desc": "Local LLM inference"},
}


def _engine(path: str = ".") -> RageBotEngine:
    return RageBotEngine(project_path=Path(path).resolve(), config=ConfigManager())


def _spin(msg: str) -> Progress:
    return Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[bold cyan]{task.description}"),
        console=console,
        transient=True
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Provider Selection (Interactive)
# ═══════════════════════════════════════════════════════════════════════════════


def _select_provider(prompt_msg: str = "Select a provider") -> str:
    """Interactive provider selection with arrow keys and mouse support."""
    choices = []
    for p in PROVIDERS:
        meta = _PROVIDER_META.get(p, {"icon": "•", "color": "white", "label": p.title()})
        choices.append(questionary.Choice(
            title=[
                ("class:icon", f"{meta['icon']} "),
                ("class:label", meta["label"]),
            ],
            value=p
        ))
    
    selected = questionary.select(
        prompt_msg,
        choices=choices,
        style=questionary.Style([
            ("icon", "fg:white"),
            ("label", "bold"),
            ("selected", "fg:cyan bold"),
        ])
    ).ask()
    
    if not selected:
        return PROVIDERS[0]
    
    meta = _PROVIDER_META.get(selected, {})
    console.print(f"  → [bold green]{meta.get('icon', '•')}  {meta.get('label', selected.title())}[/bold green]\n")
    return selected


# ═══════════════════════════════════════════════════════════════════════════════
# Model Selection (Interactive)
# ═══════════════════════════════════════════════════════════════════════════════

_MODEL_CATEGORIES: dict[str, tuple[str, str]] = {
    "openai/": ("OpenAI (GPT-OSS)", "bright_magenta"),
    "whisper": ("OpenAI (Whisper)", "magenta"),
    "llama":   ("Meta (LLaMA)", "bright_blue"),
    "gemma":   ("Google (Gemma)", "bright_cyan"),
    "mixtral": ("Mistral (Mixtral)", "bright_yellow"),
    "gemini-": ("Google Gemini", "blue"),
}


def _get_model_category(model_id: str) -> tuple[str, str]:
    for prefix, (name, color) in _MODEL_CATEGORIES.items():
        if model_id.startswith(prefix):
            return name, color
    return "Other", "white"


def _select_model(provider: str) -> str:
    """Interactive model selection with support for Ollama auto-detection."""
    from ragebot.llm.models import PROVIDER_MODELS, PROVIDER_DEFAULTS
    
    # Special handling for Ollama - auto-detect models from running server
    if provider == "ollama":
        return _select_ollama_model()
    
    models        = PROVIDER_MODELS.get(provider, [])
    default_model = PROVIDER_DEFAULTS.get(provider, "")
    if not models:
        return default_model

    console.print(Panel(f"[bold]Choose a model for [cyan]{provider.title()}[/cyan][/bold]", 
                       border_style="cyan", padding=(0, 2)))
    
    choices = []
    for m in models:
        cat_name, cat_color = _get_model_category(m["id"])
        is_default = " (DEFAULT)" if m["id"] == default_model else ""
        choices.append(questionary.Choice(
            title=[
                ("class:model", f"{m['name']}{is_default}"),
                ("class:dim", f"  [{cat_name}] "),
                ("class:dim", f"- {m['id']}"),
            ],
            value=m
        ))

    selected = questionary.select(
        "Select model:",
        choices=choices,
        style=questionary.Style([
            ("model", "bold"),
            ("dim", "grey"),
            ("selected", "fg:cyan bold"),
        ])
    ).ask()

    if not selected:
        selected = models[0]

    console.print(Panel(
        f"[bold green]✓  {selected['name']}[/bold green]\n[dim]{selected['id']}[/dim]",
        border_style="green",
        title="[bold]Selected Model[/bold]",
        title_align="left",
        padding=(0, 2)
    ))
    return selected["id"]


def _select_ollama_model() -> str:
    """Auto-detect and select from available Ollama models."""
    try:
        from ragebot.llm.ollama import OllamaProvider
        
        console.print(Panel("[bold]Discovering Ollama models...[/bold]", 
                           border_style="cyan", padding=(0, 2)))
        
        # Create a temporary provider to discover models
        provider = OllamaProvider()
        models = provider.MODELS
        
        if not models:
            show_friendly_error(
                console,
                "No Ollama Models Found",
                "Ollama is running but no models are installed.",
                "Install a model: ollama pull llama3"
            )
            return "llama3"
        
        console.print(Panel(f"[bold]Choose a model for [cyan]Ollama[/cyan][/bold]", 
                           border_style="cyan", padding=(0, 2)))
        
        choices = []
        for m in models:
            choices.append(questionary.Choice(
                title=[
                    ("class:model", m["name"]),
                    ("class:dim", f"  - {m['id']}"),
                ],
                value=m
            ))
        
        selected = questionary.select(
            "Select model:",
            choices=choices,
            style=questionary.Style([
                ("model", "bold"),
                ("dim", "grey"),
                ("selected", "fg:cyan bold"),
            ])
        ).ask()
        
        if not selected:
            selected = models[0]
        
        console.print(Panel(
            f"[bold green]✓  {selected['name']}[/bold green]\n[dim]{selected['id']}[/dim]",
            border_style="green",
            title="[bold]Selected Model[/bold]",
            title_align="left",
            padding=(0, 2)
        ))
        return selected["id"]
        
    except RuntimeError as e:
        show_friendly_error(console, "Ollama Error", str(e), "Make sure Ollama is running: ollama serve")
        return "llama3"
    except Exception as e:
        show_friendly_error(console, "Error Discovering Ollama Models", str(e))
        return "llama3"


# ═══════════════════════════════════════════════════════════════════════════════
# File Edit Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _show_diff_and_confirm(eng: RageBotEngine, file_path: str, instruction: str) -> None:
    """Ask LLM for modified file, show colored diff, prompt user to confirm."""
    with _spin(f"Generating edit for {file_path}…"):
        result = eng.apply_file_edit(file_path=file_path, instruction=instruction, write=False)

    if "error" in result:
        show_friendly_error(console, "Edit Failed", result["error"])
        return

    diff = result.get("diff", "")
    if diff == "(no changes detected)":
        show_info_badge(console, "The LLM produced no changes for that instruction.")
        return

    # Show the diff with syntax highlighting
    console.print(Panel(
        Syntax(diff, "diff", theme="monokai", line_numbers=False),
        title=f"[bold yellow]Proposed changes to [cyan]{file_path}[/cyan][/bold yellow]",
        border_style="yellow",
    ))

    if Confirm.ask("\n[bold]Write these changes to disk?[/bold]", default=False):
        write_result = eng.apply_file_edit(
            file_path=file_path, instruction=instruction, write=True
        )
        if write_result.get("written"):
            show_success_badge(console, f"[bold]{file_path}[/bold] updated and re-indexed.")
        elif "error" in write_result:
            show_friendly_error(console, "Write Failed", write_result["error"])
        else:
            show_info_badge(console, "No changes written.")
    else:
        show_info_badge(console, "Changes discarded.")


def _detect_edit_intent(user_input: str, eng: RageBotEngine) -> tuple[str | None, str | None]:
    """Detect if user wants to edit a file."""
    import re
    EDIT_VERBS = re.compile(
        r"\b(add|insert|remove|delete|rename|replace|fix|update|change|"
        r"modify|refactor|append|prepend|comment|put|write|move|rewrite)\b",
        re.IGNORECASE,
    )

    from ragebot.search.retriever import extract_file_mentions

    if not EDIT_VERBS.search(user_input):
        return None, None

    mentioned = extract_file_mentions(user_input)
    if not mentioned:
        return None, None

    # Try to resolve the first mentioned file against the index
    for mention in mentioned:
        all_files = eng.db.get_all_files()
        for f in all_files:
            fp = f["file_path"].lower().replace("\\", "/")
            mention_norm = mention.replace("\\", "/")
            if fp.endswith(mention_norm) or mention_norm in fp:
                return f["file_path"], user_input

    return None, None


# ═══════════════════════════════════════════════════════════════════════════════
# INTERACTIVE REPL
# ═══════════════════════════════════════════════════════════════════════════════

_REPL_COMMANDS: dict[str, str] = {
    "ask":      "Ask questions about your project",
    "save":     "Index and snapshot the project",
    "snapshot": "Manage snapshots (list/restore/delete)",
    "init":     "Initialize RageBot for a project",
    "search":   "Semantic search project files",
    "explain":  "Explain files or symbols",
    "docs":     "Generate documentation",
    "test":     "Generate test cases",
    "context":  "Show project overview",
    "status":   "Show index status & LLM config",
    "auth":     "Manage API keys",
    "config":   "Manage settings",
    "version":  "Show version info",
    "help":     "Show this help",
    "list":     "List available models",
    "exit":     "Exit the session",
}

def _repl_help():
    t = Table(title="⚡ Available Commands", box=None, header_style="bold cyan", show_edge=False, padding=(0, 2))
    t.add_column("Command", style="bold yellow", min_width=12)
    t.add_column("Description", style="white")
    for cmd, desc in sorted(_REPL_COMMANDS.items()):
        t.add_row(cmd, desc)
    console.print(t)
    console.print("\n[dim]Tip: Type a question directly to ask the AI about your project.[/dim]\n")

def _run_interactive_repl():
    """Main REPL loop with context-aware chat history."""
    display.banner()
    console.print(Panel(
        "[bold cyan]Welcome to RageBot[/bold cyan]  •  [dim]Interactive Mode[/dim]\n\n"
        "[dim]Type a question to ask about your project, or use a command.\n"
        "Type [bold]help[/bold] for commands, [bold]exit[/bold] or [bold]Ctrl+C[/bold] to quit.[/dim]",
        border_style="cyan", padding=(1, 3),
    ))

    session_id = f"repl_{uuid.uuid4().hex[:12]}"
    messages: list[dict] = []
    eng: RageBotEngine | None = None

    while True:
        try:
            raw_input = Prompt.ask("\n[bold cyan]❯[/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye! 👋[/dim]")
            break

        if not raw_input:
            continue

        input_stripped = raw_input
        if input_stripped.lower().startswith("ragebot "):
            input_stripped = input_stripped[8:].strip()
        elif input_stripped.lower().startswith("rage "):
            input_stripped = input_stripped[5:].strip()

        low   = input_stripped.lower()
        parts = input_stripped.split()
        cmd_name = parts[0].lower() if parts else ""

        # ── Built-in commands ─────────────────────────────────────────────
        if low in ("exit", "quit", "/exit", "/quit", "/q"):
            console.print("[dim]Goodbye! 👋[/dim]")
            break
        elif cmd_name in ("/help", "help"):
            _repl_help(); continue
        elif cmd_name == "version":
            cmd_version(); continue
        elif cmd_name == "status":
            p = parts[1] if len(parts) > 1 else "."
            cmd_status(path=p); continue
        elif cmd_name == "auth":
            _do_auth_menu(); continue
        elif cmd_name == "save":
            p = parts[1] if len(parts) > 1 else "."
            cmd_save(path=p); continue
        elif cmd_name == "init":
            p = parts[1] if len(parts) > 1 else "."
            cmd_init(path=p); continue
        elif cmd_name == "search":
            query = " ".join(parts[1:])
            if query: cmd_search(query=query)
            else: show_warning_badge(console, "Usage: search <query>")
            continue
        elif cmd_name == "explain":
            fp = parts[1] if len(parts) > 1 else ""
            if fp: cmd_explain(file_path=fp)
            else: show_warning_badge(console, "Usage: explain <file_path>")
            continue
        elif cmd_name == "docs":
            fp = parts[1] if len(parts) > 1 else ""
            if fp: cmd_docs(file_path=fp)
            else: show_warning_badge(console, "Usage: docs <file_path>")
            continue
        elif cmd_name == "test":
            fp = parts[1] if len(parts) > 1 else ""
            if fp: cmd_test(file_path=fp)
            else: show_warning_badge(console, "Usage: test <file_path>")
            continue
        elif cmd_name == "config":
            cfg_show(); continue
        elif cmd_name == "context":
            p = parts[1] if len(parts) > 1 else "."
            cmd_context(path=p); continue
        elif cmd_name == "snapshot":
            action = parts[1] if len(parts) > 1 else "list"
            snap_name = parts[2] if len(parts) > 2 else None
            cmd_snapshot(action=action, name=snap_name); continue

        # ── AI interaction ────────────────────────────────────────────────
        if eng is None:
            eng = _engine(".")

        if not (eng.project_path / ".ragebot").exists():
            show_warning_badge(console, "Project not initialized. Please run [bold]init[/bold] first.")
            continue

        # ── Detect file-edit intent ───────────────────────────────────────
        file_path, instruction = _detect_edit_intent(raw_input, eng)
        if file_path and instruction:
            _show_diff_and_confirm(eng, file_path, instruction)
            messages.append({"role": "user",      "content": raw_input})
            messages.append({"role": "assistant",  "content": f"[Edited {file_path}]"})
            continue
        elif cmd_name == "list":
            cmd_list()
            continue

        # ── Regular chat with history-aware retrieval ─────────────────────
        messages.append({"role": "user", "content": raw_input})
        eng.db.save_chat_message(session_id, "user", raw_input)
        with _spin("Thinking…"):
            try:
                response = eng.chat(messages=messages, top_k=5, session_id=session_id)
                messages.append({"role": "assistant", "content": response})
                eng.db.save_chat_message(session_id, "assistant", response)
                console.print(Panel(
                    Markdown(response),
                    title="[bold green]Ragebot[/bold green]",
                    border_style="green",
                ))
            except Exception as e:
                show_friendly_error(console, "Error", str(e))
                messages.pop()


@app.callback(invoke_without_command=True)
def _app_callback(ctx: typer.Context):
    """🤖 RageBot MCP — Intelligent Project Context Engine."""
    if ctx.invoked_subcommand is None:
        _run_interactive_repl()


# ═══════════════════════════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@app.command("init")
def cmd_init(
    path:  str  = typer.Argument(".", help="Project directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-initialization"),
):
    """🚀 Initialize RageBot. Set up project indexing and prepare for analysis."""
    try:
        eng = _engine(path)
        with _spin("Initialising RageBot…") as progress:
            task = progress.add_task("Initialising…", total=None)
            result = eng.initialize(force=force)
            progress.update(task, description=f"Initialised [bold]{result['file_count']}[/bold] files")
        show_success_badge(console, f"Initialised at [bold]{result['path']}[/bold]")
        show_info_badge(console, "RageBot tables created securely.")
        show_info_badge(console, f"[bold]{result['file_count']}[/bold] indexable files found.")
        show_info_badge(console, "Run [bold cyan]rage save[/bold cyan] to index the project.")
    except Exception as e:
        show_friendly_error(console, "Initialization Error", str(e))


@app.command("save")
def cmd_save(
    path:          str           = typer.Argument(".", help="Project directory"),
    incremental:   bool          = typer.Option(True, "--incremental/--full"),
    snapshot_name: Optional[str] = typer.Option(None, "--name", "-n", help="Custom snapshot name"),
):
    """💾 Index project files and save a snapshot."""
    try:
        eng = _engine(path)
        if not (eng.project_path / ".ragebot" / "ragebot.db").exists():
            show_info_badge(console, "Project not initialized — running init first…")
            eng.initialize()

        # Prompt for snapshot name if not provided
        if not snapshot_name:
            import time
            default_name = f"snap_{int(time.time())}"
            snapshot_name = Prompt.ask(
                "[bold]Snapshot name[/bold] [dim](press Enter for auto-generated name)[/dim]",
                default=default_name,
                show_default=True
            ).strip() or default_name

        with _spin("Indexing project…"):
            result = eng.save(incremental=incremental, snapshot_name=snapshot_name)

        table = Table(title="📊 Indexing Summary", box=None, show_header=True, header_style="bold cyan")
        table.add_column("Metric",  style="cyan",  min_width=20)
        table.add_column("Value",   style="green")
        table.add_row("Snapshot Name",    result["snapshot_name"])
        table.add_row("Files Indexed",    str(result["indexed"]))
        table.add_row("Files Skipped",    str(result["skipped"]))
        table.add_row("Tokens Estimated", str(result["token_estimate"]))
        import time as _time
        table.add_row("Timestamp",        _time.strftime("%Y-%m-%d %H:%M:%S"))
        console.print(table)
    except Exception as e:
        show_friendly_error(console, "Save Error", str(e))


@app.command("ask")
def cmd_ask(
    query:      str           = typer.Argument(..., help="Question about the project"),
    path:       str           = typer.Option(".", "--path", "-p"),
    mode:       str           = typer.Option("smart", "--mode", "-m", help="minimal|smart|full"),
    top_k:      int           = typer.Option(5,  "--top-k", "-k"),
    show_files: bool          = typer.Option(True, "--show-files/--no-files"),
    export:     Optional[str] = typer.Option(None, "--export", "-e", help="Save result as JSON"),
):
    """🔍 Ask questions about your project."""
    try:
        eng = _engine(path)
        with _spin(f"Thinking about: {query!r}…"):
            result = eng.ask(query=query, mode=mode, top_k=top_k)
        console.print(Panel(f"[bold yellow]{query}[/bold yellow]", title="❓ Query", border_style="blue"))
        answer = result.get("answer", "")
        if answer:
            console.print(Panel(Markdown(answer), title=f"💡 Answer", border_style="green"))
        if show_files and result.get("sources"):
            t = Table(title="📁 Sources", box=None, header_style="bold cyan")
            t.add_column("File", style="cyan")
            t.add_column("Score", style="yellow")
            t.add_column("Type", style="magenta")
            for s in result["sources"]:
                t.add_row(s["file"], f"{s['score']:.3f}", s["type"])
            console.print(t)
        if export:
            Path(export).write_text(json.dumps(result, indent=2))
            show_success_badge(console, f"Saved to [bold]{export}[/bold]")
    except Exception as e:
        show_friendly_error(console, "Ask Error", str(e))


@app.command("chat")
def cmd_chat(
    path:       str           = typer.Option(".", "--path", "-p"),
    session_id: Optional[str] = typer.Option(None, "--session", "-s", help="Resume a session"),
    top_k:      int           = typer.Option(5, "--top-k", "-k"),
):
    """💬 Interactive chat with context."""
    try:
        eng = _engine(path)
        sid = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        console.print(Panel(f"[bold cyan]RageBot Chat[/bold cyan] • Session: [dim]{sid}[/dim]", border_style="cyan"))
        history:  list[dict] = eng.db.get_chat_history(sid, limit=40)
        messages: list[dict] = [{"role": m["role"], "content": m["content"]} for m in history]

        while True:
            try:
                user_input = Prompt.ask("[bold cyan]You[/bold cyan]").strip()
            except (KeyboardInterrupt, EOFError):
                break
            if not user_input:
                continue
            if user_input.startswith("/"):
                cmd = user_input.lower()
                if cmd in ("/exit", "/quit"):
                    break
                elif cmd == "/clear":
                    eng.db.delete_chat_session(sid)
                    eng.clear_context_cache(sid)
                    messages = []
                    show_success_badge(console, "Session cleared.")
                    continue
                else:
                    show_warning_badge(console, f"Unknown command: {user_input}")
                    continue

            file_path, instruction = _detect_edit_intent(user_input, eng)
            if file_path and instruction:
                _show_diff_and_confirm(eng, file_path, instruction)
                messages.append({"role": "user",     "content": user_input})
                messages.append({"role": "assistant", "content": f"[Edited {file_path}]"})
                eng.db.save_chat_message(sid, "user",      user_input)
                eng.db.save_chat_message(sid, "assistant", f"[Edited {file_path}]")
                continue

            messages.append({"role": "user", "content": user_input})
            eng.db.save_chat_message(sid, "user", user_input)

            with _spin("Thinking…"):
                response = eng.chat(messages=messages, top_k=top_k, session_id=sid)

            messages.append({"role": "assistant", "content": response})
            eng.db.save_chat_message(sid, "assistant", response)
            console.print(Panel(Markdown(response), title="[bold green]Ragebot[/bold green]", border_style="green"))

    except Exception as e:
        show_friendly_error(console, "Chat Error", str(e))


@app.command("search")
def cmd_search(
    query:        str  = typer.Argument(..., help="Search query"),
    path:         str  = typer.Option(".", "--path", "-p"),
    search_type:  str  = typer.Option("semantic", "--type", "-t"),
    top_k:        int  = typer.Option(10, "--top-k", "-k"),
):
    """🔎 Semantic search."""
    try:
        from ragebot.utils.search_formatter import SearchResultFormatter

        formatter = SearchResultFormatter(console)
        eng = _engine(path)
        with _spin(f"Searching: {query!r}…"):
            results = eng.search(query=query, search_type=search_type, top_k=top_k)

        if not results:
            show_info_badge(console, "No results found.")
            return

        formatter.format_results(results, query=query)
    except Exception as e:
        show_friendly_error(console, "Search Error", str(e))


@app.command("status")
def cmd_status(path: str = typer.Argument(".", help="Project directory")):
    """📡 Check status."""
    try:
        eng = _engine(path)
        db_exists = (eng.rage_dir / "ragebot.db").exists()
        if not db_exists:
            show_warning_badge(console, f"Project at {path} is not initialized.")
            return

        s = eng.get_status()
        llm_status = "[bold green]✓ Ready[/bold green]" if s.get("llm_ready") else "[bold red]✗ Not configured[/bold red]"
        console.print(Panel(
            f"[cyan]Project:[/cyan]          {s.get('project_path')}\n"
            f"[cyan]Indexed Files:[/cyan]    {s.get('indexed_files')}\n"
            f"[cyan]Last Saved:[/cyan]       {s.get('last_saved','Never')}\n"
            f"[cyan]LLM Provider:[/cyan]     {s.get('llm_provider','N/A')}  {llm_status}",
            title="📡 RageBot Status", border_style="blue",
        ))
    except Exception as e:
        show_friendly_error(console, "Status Error", str(e))


@app.command("version")
def cmd_version():
    """📌 Show version."""
    console.print(Panel("[bold cyan]RageBot MCP[/bold cyan]  v1.0.0\nIntelligent Project Context Engine", border_style="cyan"))


@app.command("explain")
def cmd_explain(
    file_path: str = typer.Argument(...),
    symbol: Optional[str] = typer.Option(None, "--symbol", "-s"),
    path: str = typer.Option("."),
):
    """📖 Explain code."""
    try:
        eng = _engine(path)
        # Try to resolve file path against indexed files
        resolved = _resolve_file_path(eng, file_path)
        if not resolved:
            show_friendly_error(
                console, "File Not Found",
                f"'{file_path}' is not indexed.",
                "Run 'rage save' to index your project, then try again."
            )
            return
        with _spin(f"Explaining {resolved}…"):
            result = eng.explain(resolved, symbol)
        if "error" in result:
            show_friendly_error(console, "Explain Error", result["error"])
            return
        console.print(Panel(Markdown(result.get("explanation", "")), title="💡 Explanation", border_style="green"))
    except Exception as e:
        show_friendly_error(console, "Explain Error", str(e))

def _resolve_file_path(eng: RageBotEngine, file_path: str) -> Optional[str]:
    """Try to resolve a file path against the indexed files."""
    # Direct match
    if eng.db.get_file(file_path):
        return file_path
    # Normalize separators
    normalized = file_path.replace("\\", "/")
    all_files = eng.db.get_all_files()
    for f in all_files:
        fp = f["file_path"].replace("\\", "/")
        if fp == normalized or fp.endswith("/" + normalized) or fp.endswith(normalized):
            return f["file_path"]
    # Basename match
    import os
    basename = os.path.basename(file_path)
    for f in all_files:
        if os.path.basename(f["file_path"]) == basename:
            return f["file_path"]
    return None


@app.command("docs")
def cmd_docs(file_path: str = typer.Argument(...), path: str = typer.Option(".")):
    """📝 Generate docs."""
    try:
        eng = _engine(path)
        with _spin("Generating docs…"):
            docs = eng.generate_docs(file_path)
        console.print(Panel(Markdown(docs), border_style="cyan"))
    except Exception as e:
        show_friendly_error(console, "Docs Error", str(e))

from ragebot.storage.session_manager import SessionManager

@app.command("history")
def cmd_history():
    """📜 List chat sessions. Select one to continue chatting."""
    try:
        engine = _engine(".")
        session_mgr = SessionManager(engine.db)
        selected_sid = session_mgr.display_sessions_interactive()
        if selected_sid:
            # Show history then continue chatting with preserved context
            session_mgr.view_session_full(selected_sid)
            console.print("\n[bold cyan]Continue chatting in this session? Type your message or /exit to quit.[/bold cyan]\n")
            _continue_chat_session(engine, selected_sid)
    except Exception as e:
        show_friendly_error(console, "History Error", str(e))

@app.command("show")
def cmd_show(session_number: int = typer.Argument(..., help="Session number from 'rage history'")):
    """👁️ Show full chat history for a session by number."""
    try:
        engine = _engine(".")
        session_mgr = SessionManager(engine.db)
        session_mgr.show_session_by_number(session_number)
    except Exception as e:
        show_friendly_error(console, "Show Error", str(e))

@app.command("delete")
def cmd_delete(session_number: int = typer.Argument(..., help="Session number from 'rage history'")):
    """🗑️ Delete a chat session by number."""
    try:
        engine = _engine(".")
        session_mgr = SessionManager(engine.db)
        session_mgr.delete_session_by_number(session_number)
    except Exception as e:
        show_friendly_error(console, "Delete Error", str(e))

def _continue_chat_session(eng: RageBotEngine, session_id: str):
    """Continue an existing chat session with full context preservation."""
    history = eng.db.get_chat_history(session_id, limit=100)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session saved. Goodbye! 👋[/dim]")
            break
        if not user_input:
            continue
        if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
            console.print("[dim]Session saved. Goodbye! 👋[/dim]")
            break

        file_path, instruction = _detect_edit_intent(user_input, eng)
        if file_path and instruction:
            _show_diff_and_confirm(eng, file_path, instruction)
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": f"[Edited {file_path}]"})
            eng.db.save_chat_message(session_id, "user", user_input)
            eng.db.save_chat_message(session_id, "assistant", f"[Edited {file_path}]")
            continue

        messages.append({"role": "user", "content": user_input})
        eng.db.save_chat_message(session_id, "user", user_input)

        with _spin("Thinking…"):
            try:
                response = eng.chat(messages=messages, top_k=5, session_id=session_id)
            except Exception as e:
                show_friendly_error(console, "Chat Error", str(e))
                messages.pop()
                continue

        messages.append({"role": "assistant", "content": response})
        eng.db.save_chat_message(session_id, "assistant", response)
        console.print(Panel(Markdown(response), title="[bold green]Ragebot[/bold green]", border_style="green"))

from ragebot.utils.config_display import ConfigurationDisplay

@app.command("config")
def cmd_config(
    edit: bool = typer.Option(False, "--edit", "-e", help="Edit ignore patterns interactively"),
    path: str = typer.Argument(".", help="Project directory"),
):
    """⚙️ Show or edit configuration."""
    try:
        config = ConfigManager()
        if edit:
            _edit_ignore_patterns(config)
        else:
            cd = ConfigurationDisplay(config)
            engine = _engine(path)
            cd.display_runtime_config(engine)
    except Exception as e:
        show_friendly_error(console, "Config Error", str(e))

def _edit_ignore_patterns(config: ConfigManager):
    """Interactive ignore pattern editor."""
    current = config.get_ignore_patterns()
    console.print(Panel(
        "[bold cyan]Current Ignore Patterns[/bold cyan]",
        border_style="cyan", padding=(0, 2)
    ))
    for i, p in enumerate(current, 1):
        console.print(f"  [yellow]{i:>3}.[/yellow] {p}")

    console.print("\n[dim]Options: [bold]add[/bold] <pattern>, [bold]remove[/bold] <number>, [bold]done[/bold][/dim]\n")
    while True:
        try:
            action = Prompt.ask("[bold cyan]Edit[/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not action or action.lower() == "done":
            break
        if action.lower().startswith("add "):
            pattern = action[4:].strip()
            if pattern and pattern not in current:
                current.append(pattern)
                config.set("ignore_patterns", ",".join(current))
                show_success_badge(console, f"Added: {pattern}")
            elif pattern in current:
                show_warning_badge(console, f"'{pattern}' already exists.")
        elif action.lower().startswith("remove "):
            try:
                idx = int(action[7:].strip()) - 1
                if 0 <= idx < len(current):
                    removed = current.pop(idx)
                    config.set("ignore_patterns", ",".join(current))
                    show_success_badge(console, f"Removed: {removed}")
                else:
                    show_warning_badge(console, "Invalid number.")
            except ValueError:
                show_warning_badge(console, "Usage: remove <number>")
        else:
            show_warning_badge(console, "Usage: add <pattern> | remove <number> | done")

from ragebot.llm.provider_manager import ProviderManager

@app.command("model")
def cmd_model():
    """🔄 Switch between available models for the current provider."""
    try:
        config = ConfigManager()
        provider_mgr = ProviderManager(config)
        provider = provider_mgr.get_current_provider()
        
        if provider == "none":
            show_warning_badge(console, "No LLM provider configured. Run: rage auth")
            return
        
        models = provider_mgr.list_available_models(provider)
        if not models:
            show_warning_badge(console, f"No models available for {provider}.")
            return
        
        current_model = provider_mgr.get_current_model()
        
        choices = []
        for m in models:
            is_current = " ● (active)" if m["id"] == current_model else ""
            desc = m.get("desc", m.get("description", ""))
            choices.append(questionary.Choice(
                title=[
                    ("class:model", f"{m['name']}{is_current}"),
                    ("class:dim", f"  - {m['id']}"),
                    ("class:dim", f"  {desc}" if desc else ""),
                ],
                value=m["id"]
            ))
        
        console.print(Panel(
            f"[bold]Select a model for [cyan]{provider.title()}[/cyan][/bold]\n"
            f"[dim]Current: {current_model}[/dim]",
            border_style="cyan", padding=(0, 2)
        ))
        
        selected = questionary.select(
            "Choose model:",
            choices=choices,
            style=questionary.Style([
                ("model", "bold"),
                ("dim", "grey"),
                ("selected", "fg:cyan bold"),
            ])
        ).ask()
        
        if selected and selected != current_model:
            if provider_mgr.switch_model(selected):
                show_success_badge(console, f"Switched to [bold]{selected}[/bold]")
            else:
                show_friendly_error(console, "Switch Failed", provider_mgr.get_last_error() or "Unknown error")
        elif selected == current_model:
            show_info_badge(console, f"Already using {selected}")
    except Exception as e:
        show_friendly_error(console, "Model Error", str(e))

@app.command("providers")
def cmd_providers():
    """📋 Show all available providers and their status."""
    try:
        config = ConfigManager()
        provider_mgr = ProviderManager(config)
        
        table = Table(title="📋 Available Providers", box=None, header_style="bold cyan")
        table.add_column("Provider", style="cyan", width=17)
        table.add_column("Label", style="white", width=30)
        table.add_column("Status", style="green", width=20)
        table.add_column("Default Model", style="dim", width=30)
        
        current = provider_mgr.get_current_provider()
        
        provider_info = {
            "gemini": {"label": "Google Gemini", "default": "gemini-2.0-flash"},
            "groq": {"label": "Groq (OpenAI-Compatible)", "default": "openai/gpt-oss-120b"},
            "ollama": {"label": "Ollama (Local)", "default": "llama3"},
        }
        
        for pid, info in provider_info.items():
            if pid == "ollama":
                model_set = config.get("ollama_model", "")
                status = "✓ Configured" if model_set else "○ Not Configured"
            else:
                api_key = config.get(f"{pid}_api_key", "")
                status = "✓ Configured" if api_key else "○ Not Configured"
            
            display_name = f"★ {pid}" if pid == current else f"  {pid}"
            table.add_row(display_name, info["label"], status, info["default"])
        
        console.print(table)
    except Exception as e:
        show_friendly_error(console, "Providers Error", str(e))

@app.command("test")
def cmd_test(file_path: str = typer.Argument(...), path: str = typer.Option(".")):
    """🧪 Generate tests."""
    try:
        eng = _engine(path)
        with _spin("Generating tests…"):
            tests = eng.generate_tests(file_path)
        console.print(Panel(Syntax(tests, "python"), border_style="cyan"))
    except Exception as e:
        show_friendly_error(console, "Test Error", str(e))


@app.command("context")
def cmd_context(path: str = typer.Option("."), tree: bool = typer.Option(False)):
    """📋 Project overview."""
    try:
        eng = _engine(path)
        if tree:
            console.print(eng.get_file_tree()["tree"])
        else:
            stats = eng.get_project_overview()
            for k, v in stats.items():
                console.print(f"{k}: {v}")
    except Exception as e:
        show_friendly_error(console, "Context Error", str(e))


def cfg_show():
    """Display current configuration."""
    cfg = ConfigManager()
    all_cfg = cfg.get_all()
    t = Table(title="⚙️  RageBot Config", box=None, header_style="bold cyan", show_edge=False, padding=(0, 2))
    t.add_column("Key",   style="cyan",  min_width=28)
    t.add_column("Value", style="white")
    for k, v in sorted(all_cfg.items()):
        t.add_row(k, v)
    console.print(t)


@app.command("list")
def cmd_list():
    """📜 List models."""
    try:
        cfg = ConfigManager()
        provider = cfg.get("llm_provider", "gemini")
        from ragebot.llm.models import PROVIDER_MODELS
        models = PROVIDER_MODELS.get(provider, [])
        
        table = Table(title=f"📜 Available Models for {provider.title()}", box=None, header_style="bold cyan")
        table.add_column("Model Name", style="bold yellow")
        table.add_column("ID", style="dim")
        table.add_column("Description")
        
        current_model = cfg.get(f"{provider}_model", "")
        
        for m in models:
            is_active = "[green]●[/green] " if m["id"] == current_model else "  "
            table.add_row(f"{is_active}{m['name']}", m["id"], m["description"])
        
        console.print(table)
    except Exception as e:
        show_friendly_error(console, "List Error", str(e))


@app.command("snapshot")
def cmd_snapshot(
    action: str = typer.Argument("list", help="list, restore, delete"),
    name:   Optional[str] = typer.Argument(None, help="Snapshot name"),
    path:   str = typer.Option(".", "--path", "-p"),
):
    """📸 Manage snapshots."""
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
            t.add_column("", style="yellow", width=3)
            t.add_column("Name", style="cyan")
            t.add_column("Created", style="yellow")
            t.add_column("Files", style="green")
            t.add_column("Size", style="dim")
            for s in snaps:
                marker = "★" if s.get("active") else " "
                name_style = f"[bold cyan]{s['name']}[/bold cyan]" if s.get("active") else s["name"]
                t.add_row(marker, name_style, s["created"], str(s["files"]), s["size"])
            console.print(t)
            console.print("[dim]★ = currently active snapshot[/dim]")
        elif action == "restore":
            if not name:
                show_friendly_error(console, "Argument Error", "Snapshot name required for restore.")
                return
            sm.restore(name)
            show_success_badge(console, f"Restored snapshot: [bold]{name}[/bold]")
        elif action == "delete":
            if not name:
                show_friendly_error(console, "Argument Error", "Snapshot name required for delete.")
                return
            if Confirm.ask(f"Delete snapshot [bold]{name}[/bold]?", default=False):
                sm.delete(name)
                show_success_badge(console, f"Deleted snapshot: [bold]{name}[/bold]")
        else:
            show_friendly_error(console, "Unknown Action", f"Use: list, restore, delete")
    except Exception as e:
        show_friendly_error(console, "Snapshot Error", str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH (Interactive)
# ═══════════════════════════════════════════════════════════════════════════════

auth_app = typer.Typer(help="🔐 Manage API keys.", invoke_without_command=True)
app.add_typer(auth_app, name="auth")

def _do_auth_menu():
    """Interactive auth menu with provider status."""
    cfg = ConfigManager()
    provider = cfg.get("llm_provider", "none")
    model = cfg.get(f"{provider}_model", "N/A")
    
    console.print()
    console.print(Panel(
        f"[bold cyan]🔐  RageBot Auth Manager[/bold cyan]",
        subtitle=f"[yellow]{provider}[/yellow] @ [green]{model}[/green]",
        subtitle_align="right",
        border_style="cyan",
        padding=(1, 3)
    ))
    choice = questionary.select(
        "Select an action:",
        choices=["Login", "Status", "Switch"],
        style=questionary.Style([("selected", "fg:cyan bold")])
    ).ask()
    
    if   choice == "Login":  _do_login_interactive()
    elif choice == "Status": _do_auth_status()
    elif choice == "Switch": _do_switch_interactive()

@auth_app.callback()
def auth_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        _do_auth_menu()
        
from ragebot.auth.provider_auth import ProviderAuthenticator

def _do_login_interactive(provider: str | None = None):
    """Login to a provider — delegates entirely to ProviderAuthenticator."""
    config = ConfigManager()
    provider_mgr = ProviderManager(config)
    authenticator = ProviderAuthenticator(config, provider_mgr)
    
    if not provider:
        provider = _select_provider()
    
    success, message = authenticator.authenticate_provider(provider)
    
    if success:
        show_success_badge(console, message)
    else:
        show_friendly_error(console, "Authentication Failed", message)

def _do_auth_status():
    """Show authentication status for all providers."""
    cfg = ConfigManager()
    active = cfg.get("llm_provider", "none")
    console.print()
    for p in PROVIDERS:
        if p == "ollama":
            status = "[green]✓ Configured[/green]" if cfg.get(f"{p}_model") else "[yellow]○ Not configured[/yellow]"
        else:
            key = cfg.get(f"{p}_api_key", "")
            status = "[green]✓ Configured[/green]" if key else "[yellow]○ Missing key[/yellow]"
        act = " ★ [bold cyan](active)[/bold cyan]" if p == active else ""
        console.print(f"  {p.title():<12} {status}{act}")
    console.print()

def _do_switch_interactive():
    """Switch active provider."""
    p = _select_provider("Select provider to activate")
    ConfigManager().set("llm_provider", p)
    show_success_badge(console, f"Switched to {p.title()}")




# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINTS
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Main entry point for `rage` command."""
    app()

def main_interactive() -> None:
    """Main entry point for `ragebot` command (launches interactive REPL)."""
    _run_interactive_repl()


if __name__ == "__main__":
    main()
