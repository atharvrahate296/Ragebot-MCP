"""
RageBot MCP — CLI Entry Point
══════════════════════════════
Modern interactive CLI inspired by Gemini CLI and Claude Code.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.syntax import Syntax
from rich.table import Table

from ragebot.core.config   import ConfigManager
from ragebot.core.engine   import RageBotEngine
from ragebot.utils.display import Display
import questionary


# ── App & globals ─────────────────────────────────────────────────────────────
app = typer.Typer(
    name="rage",
    help="🤖 [bold cyan]RageBot MCP[/bold cyan] — Intelligent Project Context Engine",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=False,
)
console = Console()
display = Display()

PROVIDERS = ["gemini", "groq"]


def _engine(path: str = ".") -> RageBotEngine:
    return RageBotEngine(project_path=Path(path).resolve(), config=ConfigManager())


def _spin(msg: str) -> Progress:
    return Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[bold cyan]{task.description}"),
        console=console,
        transient=True
    )


_PROVIDER_META = {
    "gemini": {"icon": "✦", "color": "blue",  "label": "Google Gemini", "desc": "Google's multimodal AI"},
    "groq":   {"icon": "⚡", "color": "green", "label": "Groq",          "desc": "Ultra-fast LLM inference"},
}


def _select_provider(prompt_msg: str = "Select a provider") -> str:
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
            ("icon", f"fg:{_PROVIDER_META['gemini']['color']}"),
            ("label", "bold"),
            ("selected", "fg:cyan bold"),
        ])
    ).ask()
    
    if not selected:
        return PROVIDERS[0]
        
    meta = _PROVIDER_META.get(selected, {})
    console.print(f"  → [bold green]{meta.get('icon', '•')}  {meta.get('label', selected.title())}[/bold green]\n")
    return selected


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
    from ragebot.llm.models import PROVIDER_MODELS, PROVIDER_DEFAULTS
    models        = PROVIDER_MODELS.get(provider, [])
    default_model = PROVIDER_DEFAULTS.get(provider, "")
    if not models:
        return default_model

    console.print(Panel(f"[bold]Choose a model for [cyan]{provider.title()}[/cyan][/bold]", border_style="cyan", padding=(0, 2)))
    current_cat = ""
    for i, m in enumerate(models, 1):
        cat_name, cat_color = _get_model_category(m["id"])
        if cat_name != current_cat:
            current_cat = cat_name
            console.print(Rule(f"[bold {cat_color}]{cat_name}[/bold {cat_color}]", style=cat_color))
        default_badge = "  [black on green] DEFAULT [/black on green]" if m["id"] == default_model else ""
        console.print(f"  [bold yellow]{i:>2}[/bold yellow]  │  [bold]{m['name']}[/bold]{default_badge}\n       │  [dim]{m['id']}[/dim]\n       │  {m['description']}")
        console.print()
    console.print(Rule(style="dim"))
    choice   = Prompt.ask(f"[bold]Select model [dim](1-{len(models)}, default=1)[/dim][/bold]", default="1")
    valid    = [str(i) for i in range(1, len(models) + 1)]
    selected = models[int(choice) - 1] if choice in valid else models[0]

    console.print(Panel(f"[bold green]✓  {selected['name']}[/bold green]\n[dim]{selected['id']}[/dim]", border_style="green", title="[bold]Selected Model[/bold]", title_align="left", padding=(0, 2)))
    return selected_id


# ═══════════════════════════════════════════════════════════════════════════════
# File-edit helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _show_diff_and_confirm(eng: RageBotEngine, file_path: str, instruction: str) -> None:
    """
    Ask the LLM for the modified file, show a coloured diff, then
    prompt the user to confirm before writing to disk.
    """
    with _spin(f"Generating edit for {file_path}…"):
        result = eng.apply_file_edit(file_path=file_path, instruction=instruction, write=False)

    if "error" in result:
        display.error(result["error"])
        return

    diff = result.get("diff", "")
    if diff == "(no changes detected)":
        display.info("The LLM produced no changes for that instruction.")
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
            display.success(
                f"[bold]{file_path}[/bold] updated and re-indexed."
            )
        elif "error" in write_result:
            display.error(write_result["error"])
        else:
            display.info("No changes written.")
    else:
        display.info("Changes discarded.")


def _detect_edit_intent(
    user_input: str,
    eng: RageBotEngine,
) -> tuple[str | None, str | None]:
    """
    Heuristically detect if the user wants to edit a file.

    Returns (file_path, instruction) if an edit intent is detected,
    otherwise (None, None).

    Strategy:
    - Look for verbs: add, insert, remove, delete, rename, replace, fix,
      update, change, modify, refactor, append, prepend, comment
    - Combined with a file mention in the same message.
    """
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
    "ask":      "Ask a question about your project",
    "save":     "Index/snapshot the project",
    "init":     "Initialise RageBot for a project",
    "search":   "Search project files",
    "explain":  "Explain a file or symbol",
    "docs":     "Generate documentation",
    "test":     "Generate test cases",
    "diff":     "Explain a git diff",
    "context":  "Show project structure/summary",
    "status":   "Show index & LLM health",
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
    display.banner()
    console.print(Panel(
        "[bold cyan]Welcome to RageBot[/bold cyan]  •  [dim]Interactive Mode[/dim]\n\n"
        "[dim]Type a question to ask about your project, or use a command.\n"
        "Type [bold]help[/bold] for commands, [bold]exit[/bold] or [bold]Ctrl+C[/bold] to quit.[/dim]",
        border_style="cyan", padding=(1, 3),
    ))

    # Each REPL run gets a stable session ID so context cache is keyed correctly
    session_id = f"repl_{uuid.uuid4().hex[:12]}"
    messages:  list[dict] = []
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
        if input_stripped.lower().startswith("rage "):
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
            else: display.warning("Usage: search <query>")
            continue
        elif cmd_name == "explain":
            fp = parts[1] if len(parts) > 1 else ""
            if fp: cmd_explain(file_path=fp)
            else: display.warning("Usage: explain <file_path>")
            continue
        elif cmd_name == "docs":
            fp = parts[1] if len(parts) > 1 else ""
            if fp: cmd_docs(file_path=fp)
            else: display.warning("Usage: docs <file_path>")
            continue
        elif cmd_name == "test":
            fp = parts[1] if len(parts) > 1 else ""
            if fp: cmd_test(file_path=fp)
            else: display.warning("Usage: test <file_path>")
            continue
        elif cmd_name == "config":
            cfg_show(); continue
        elif cmd_name == "context":
            p = parts[1] if len(parts) > 1 else "."
            cmd_context(path=p); continue

        # ── AI interaction ────────────────────────────────────────────────
        # Lazily create engine on first non-command message
        if eng is None:
            eng = _engine(".")

        if not (eng.project_path / ".ragebot").exists():
            display.warning("Project not initialized. Please run [bold]init[/bold] first.")
            continue

        # ── Detect file-edit intent ───────────────────────────────────────
        file_path, instruction = _detect_edit_intent(raw_input, eng)
        if file_path and instruction:
            _show_diff_and_confirm(eng, file_path, instruction)
            # Add to history so context carries forward
            messages.append({"role": "user",      "content": raw_input})
            messages.append({"role": "assistant",  "content": f"[Edited {file_path}]"})
            continue
        elif cmd_name == "list":
            cmd_list()
            continue

        # ── Regular chat with history-aware retrieval ─────────────────────
        messages.append({"role": "user", "content": raw_input})
        with _spin("Thinking…"):
            try:
                response = eng.chat(
                    messages=messages,
                    top_k=5,
                    session_id=session_id,
                )
                messages.append({"role": "assistant", "content": response})
                console.print(Panel(
                    Markdown(response),
                    title="[bold green]RageBot[/bold green]",
                    border_style="green",
                ))
            except Exception as e:
                display.error(f"Error: {e}")
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
    force: bool = typer.Option(False, "--force", "-f", help="Force re-init"),
):
    """🚀 Initialise RageBot for a project directory."""
    try:
        eng = _engine(path)
        with _spin("Initialising RageBot…") as progress:
            task = progress.add_task("Initialising…", total=None)
            result = eng.initialize(force=force)
            progress.update(task, description=f"Initialised [bold]{result['file_count']}[/bold] files")
        display.success(f"Initialised at [bold]{result['path']}[/bold]")
        display.info("RageBot tables created securely.")
        display.info(f"[bold]{result['file_count']}[/bold] indexable files found.")
        display.info("Run [bold cyan]rage save[/bold cyan] to index the project.")
    except Exception as e:
        display.error(f"Error during init: {e}")


@app.command("save")
def cmd_save(
    path:          str           = typer.Argument(".", help="Project directory"),
    incremental:   bool          = typer.Option(True, "--incremental/--full"),
    snapshot_name: Optional[str] = typer.Option(None, "--name", "-n"),
):
    """💾 Index the project and save a context snapshot."""
    try:
        eng = _engine(path)
        if not (eng.project_path / ".ragebot" / "ragebot.db").exists():
            display.info("Project not initialized — running init first…")
            eng.initialize()

        with _spin("Indexing project…"):
            result = eng.save(incremental=incremental, snapshot_name=snapshot_name)

        table = Table(title="📊 Indexing Summary", box=None, show_header=True, header_style="bold cyan")
        table.add_column("Metric",  style="cyan",  min_width=20)
        table.add_column("Value",   style="green")
        table.add_row("Files Indexed",    str(result["indexed"]))
        table.add_row("Files Skipped",    str(result["skipped"]))
        table.add_row("Snapshot Name",    result["snapshot_name"])
        table.add_row("Tokens Estimated", str(result["token_estimate"]))
        console.print(table)
    except Exception as e:
        display.error(f"Error during save: {e}")


@app.command("ask")
def cmd_ask(
    query:      str           = typer.Argument(..., help="Question about the project"),
    path:       str           = typer.Option(".", "--path", "-p"),
    mode:       str           = typer.Option("smart", "--mode", "-m", help="minimal|smart|full"),
    top_k:      int           = typer.Option(5,  "--top-k", "-k"),
    show_files: bool          = typer.Option(True, "--show-files/--no-files"),
    export:     Optional[str] = typer.Option(None, "--export", "-e", help="Save result as JSON"),
    markdown:   bool          = typer.Option(True, "--markdown/--plain"),
):
    """🔍 Ask a natural language question about the project."""
    try:
        eng = _engine(path)
        with _spin(f"Thinking about: {query!r}…"):
            result = eng.ask(query=query, mode=mode, top_k=top_k)
        console.print(Panel(f"[bold yellow]{query}[/bold yellow]", title="❓ Query", border_style="blue"))
        answer = result.get("answer", "")
        if answer:
            if markdown:
                console.print(Panel(Markdown(answer), title=f"💡 Answer  [dim]({result.get('provider','')})[/dim]", border_style="green"))
            else:
                console.print(Panel(answer, title="💡 Answer", border_style="green"))
        if show_files and result.get("sources"):
            t = Table(title="📁 Sources", box=None, header_style="bold cyan")
            t.add_column("File", style="cyan"); t.add_column("Score", style="yellow"); t.add_column("Type", style="magenta")
            for s in result["sources"]:
                t.add_row(s["file"], f"{s['score']:.3f}", s["type"])
            console.print(t)
        if export:
            Path(export).write_text(json.dumps(result, indent=2))
            display.success(f"Saved to [bold]{export}[/bold]")
    except Exception as e:
        display.error(f"Error: {e}")


@app.command("chat")
def cmd_chat(
    path:       str           = typer.Option(".", "--path", "-p"),
    session_id: Optional[str] = typer.Option(None, "--session", "-s", help="Resume a session ID"),
    top_k:      int           = typer.Option(5, "--top-k", "-k"),
):
    """💬 Start an interactive multi-turn chat session."""
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
                    display.success("Session cleared.")
                    continue
                else:
                    display.warning(f"Unknown command: {user_input}")
                    continue

            # Detect edit intent before sending to LLM
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
            console.print(Panel(Markdown(response), title="[bold green]RageBot[/bold green]", border_style="green"))

    except Exception as e:
        display.error(f"Error: {e}")


@app.command("search")
def cmd_search(
    query:        str  = typer.Argument(..., help="Search query"),
    path:         str  = typer.Option(".", "--path", "-p"),
    search_type:  str  = typer.Option("semantic", "--type", "-t"),
    top_k:        int  = typer.Option(10, "--top-k", "-k"),
    show_preview: bool = typer.Option(True, "--preview/--no-preview"),
):
    """🔎 Search project files."""
    try:
        eng = _engine(path)
        with _spin(f"Searching: {query!r}…"):
            results = eng.search(query=query, search_type=search_type, top_k=top_k)
        t = Table(title="🔎 Results", box=None, header_style="bold cyan")
        t.add_column("File"); t.add_column("Score"); t.add_column("Preview")
        for r in results:
            t.add_row(r.get("file",""), f"{r.get('score',0):.3f}", r.get("preview","")[:80])
        console.print(t)
    except Exception as e:
        display.error(f"Error: {e}")


@app.command("status")
def cmd_status(path: str = typer.Argument(".", help="Project directory")):
    """📡 Show index status and LLM health."""
    try:
        eng = _engine(path)
        db_exists = (eng.rage_dir / "ragebot.db").exists()
        if not db_exists:
            display.warning(f"Project at {path} is not initialized.")
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
        display.error(f"Error getting status: {e}")


@app.command("version")
def cmd_version():
    console.print(Panel("[bold cyan]RageBot MCP[/bold cyan]  v1.0.0\nIntelligent Project Context Engine", border_style="cyan"))


# ── EXPLAIN ───────────────────────────────────────────────────────────────────
@app.command("explain")
def cmd_explain(file_path: str, symbol: Optional[str] = None, path: str = "."):
    """📖 Explain a file or symbol."""
    try:
        eng = _engine(path)
        with _spin(f"Explaining {file_path}…"):
            result = eng.explain(file_path, symbol)
        if "error" in result:
            display.error(result["error"]); return
        console.print(Panel(Markdown(result.get("explanation", "")), title="💡 Explanation", border_style="green"))
    except Exception as e:
        display.error(f"Error: {e}")


# ── DOCS / TEST ───────────────────────────────────────────────────────────────
@app.command("docs")
def cmd_docs(file_path: str, path: str = ".", output: Optional[str] = None):
    """📝 Generate documentation."""
    try:
        eng = _engine(path)
        with _spin("Generating docs…"):
            docs = eng.generate_docs(file_path)
        console.print(Panel(Markdown(docs), border_style="cyan"))
    except Exception as e:
        display.error(f"Error: {e}")


@app.command("test")
def cmd_test(file_path: str, path: str = ".", output: Optional[str] = None):
    """🧪 Generate tests."""
    try:
        eng = _engine(path)
        with _spin("Generating tests…"):
            tests = eng.generate_tests(file_path)
        console.print(Panel(Syntax(tests, "python"), border_style="cyan"))
    except Exception as e:
        display.error(f"Error: {e}")


@app.command("context")
def cmd_context(path: str = ".", tree: bool = False):
    """📋 Show project context."""
    try:
        eng = _engine(path)
        if tree:
            console.print(eng.get_file_tree()["tree"])
        else:
            stats = eng.get_project_overview()
            for k, v in stats.items():
                console.print(f"{k}: {v}")
    except Exception as e:
        display.error(f"Error: {e}")


# ── CONFIG SHOW ───────────────────────────────────────────────────────────────
def cfg_show():
    cfg = ConfigManager()
    all_cfg = cfg.get_all()
    t = Table(title="⚙️  RageBot Config", box=None, header_style="bold cyan", show_edge=False, padding=(0, 2))
    t.add_column("Key",   style="cyan",  min_width=28)
    t.add_column("Value", style="white")
    for k, v in sorted(all_cfg.items()):
        t.add_row(k, str(v))
    console.print(t)



@app.command("list")
def cmd_list():
    """📜 List available models for the current provider."""
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
        display.error(f"Error listing models: {e}")

# ── AUTH ──────────────────────────────────────────────────────────────────────
auth_app = typer.Typer(help="🔐 Manage API keys", invoke_without_command=True)
app.add_typer(auth_app, name="auth")

def _do_auth_menu():
    console.print()
    console.print(Panel("[bold cyan]🔐  RageBot Auth Manager[/bold cyan]", border_style="cyan", padding=(1, 3)))
    choice = Prompt.ask("\n[bold]1. Login  2. Logout  3. Status  4. Switch[/bold]", choices=["1","2","3","4"])
    if   choice == "1": _do_login_interactive()
    elif choice == "2": _do_logout_interactive()
    elif choice == "3": _do_auth_status()
    elif choice == "4": _do_switch_interactive()

@auth_app.callback()
def auth_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        _do_auth_menu()

def _do_login_interactive(provider: str | None = None):
    import getpass
    if not provider:
        provider = _select_provider()
    key = getpass.getpass("  API Key: ").strip()
    if key:
        cfg   = ConfigManager()
        cfg.set(f"{provider}_api_key", key)
        model = _select_model(provider)
        cfg.set(f"{provider}_model", model)
        cfg.set("llm_provider", provider)
        display.success("Authenticated!")

def _do_auth_status():
    cfg    = ConfigManager()
    active = cfg.get("llm_provider", "none")
    for p in PROVIDERS:
        key = cfg.get(f"{p}_api_key", "")
        act = " ★" if p == active else ""
        console.print(f"{p}: {'[green]OK[/green]' if key else '[red]Missing[/red]'}{act}")

def _do_logout_interactive():
    p = _select_provider()
    ConfigManager().delete_secret(f"{p}_api_key")
    display.success("Logged out.")

def _do_switch_interactive():
    p = _select_provider()
    ConfigManager().set("llm_provider", p)
    display.success(f"Switched to {p}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()