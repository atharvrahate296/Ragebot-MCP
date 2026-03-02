"""
RageBot MCP — CLI Entry Point
══════════════════════════════
Commands follow the pattern of modern AI CLIs (Gemini CLI, GitHub Copilot CLI).

  rage init            — bootstrap a project
  rage save            — index / snapshot
  rage ask             — one-shot question
  rage chat            — interactive multi-turn chat
  rage search          — file search (semantic | keyword | hybrid)
  rage explain         — explain a file or symbol
  rage docs            — generate documentation
  rage test            — generate test cases
  rage diff            — explain a git diff
  rage context         — show project structure / summary / file info
  rage export          — export context packs for AI agents
  rage snapshots       — manage snapshots
  rage status          — index & LLM health
  rage watch           — auto-watch & re-index
  rage clean           — purge cache / index
  rage auth            — manage API keys securely
  rage config          — manage non-secret settings
  rage mcp             — start MCP server
  rage version         — version info
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
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table

from ragebot.core.config  import ConfigManager
from ragebot.core.engine  import RageBotEngine
from ragebot.utils.display import Display

# ── App & globals ─────────────────────────────────────────────────────────────
app = typer.Typer(
    name="rage",
    help="🤖 [bold cyan]RageBot MCP[/bold cyan] — Intelligent Project Context Engine",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)
console = Console()
display = Display()


def _engine(path: str = ".") -> RageBotEngine:
    return RageBotEngine(
        project_path=Path(path).resolve(),
        config=ConfigManager(),
    )


def _spin(msg: str) -> Progress:
    return Progress(SpinnerColumn(), TextColumn(f"[cyan]{msg}"), console=console, transient=True)


# ═══════════════════════════════════════════════════════════════════════════════
# INIT
# ═══════════════════════════════════════════════════════════════════════════════
@app.command("init")
def cmd_init(
    path:  str  = typer.Argument(".", help="Project directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Force re-init"),
):
    """🚀 Initialise RageBot for a project directory."""
    eng = _engine(path)
    with _spin("Initialising…"):
        result = eng.initialize(force=force)
    display.success(f"Initialised at [bold]{result['path']}[/bold]")
    display.info(f"[bold]{result['file_count']}[/bold] indexable files found.")
    display.info("Run [bold cyan]rage save[/bold cyan] to index the project.")


# ═══════════════════════════════════════════════════════════════════════════════
# SAVE
# ═══════════════════════════════════════════════════════════════════════════════
@app.command("save")
def cmd_save(
    path:          str            = typer.Argument(".", help="Project directory"),
    incremental:   bool           = typer.Option(True, "--incremental/--full"),
    snapshot_name: Optional[str]  = typer.Option(None, "--name", "-n"),
):
    """💾 Index the project and save a context snapshot."""
    eng = _engine(path)
    with _spin("Indexing project…"):
        result = eng.save(incremental=incremental, snapshot_name=snapshot_name)

    table = Table(title="📊 Indexing Summary", box=None, show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="cyan", min_width=20)
    table.add_column("Value",  style="green")
    table.add_row("Files Indexed",    str(result["indexed"]))
    table.add_row("Files Skipped",    str(result["skipped"]))
    table.add_row("Snapshot Name",    result["snapshot_name"])
    table.add_row("Tokens Estimated", str(result["token_estimate"]))
    console.print(table)


# ═══════════════════════════════════════════════════════════════════════════════
# ASK
# ═══════════════════════════════════════════════════════════════════════════════
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
        t.add_column("File",      style="cyan")
        t.add_column("Score",     style="yellow")
        t.add_column("Type",      style="magenta")
        for s in result["sources"]:
            t.add_row(s["file"], f"{s['score']:.3f}", s["type"])
        console.print(t)

    if export:
        Path(export).write_text(json.dumps(result, indent=2))
        display.success(f"Saved to [bold]{export}[/bold]")


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT  (interactive multi-turn)
# ═══════════════════════════════════════════════════════════════════════════════
@app.command("chat")
def cmd_chat(
    path:       str           = typer.Option(".", "--path", "-p"),
    session_id: Optional[str] = typer.Option(None, "--session", "-s", help="Resume a session ID"),
    top_k:      int           = typer.Option(5, "--top-k", "-k"),
):
    """💬 Start an interactive multi-turn chat session about the project."""
    eng = _engine(path)
    sid = session_id or f"sess_{uuid.uuid4().hex[:8]}"

    console.print(Panel(
        f"[bold cyan]RageBot Chat[/bold cyan]  •  Session: [dim]{sid}[/dim]\n"
        "[dim]Type your question. Commands: /exit  /history  /clear  /export[/dim]",
        border_style="cyan",
    ))

    # Reload history
    history: list[dict] = eng.db.get_chat_history(sid, limit=40)
    messages: list[dict] = [{"role": m["role"], "content": m["content"]} for m in history]
    if history:
        display.info(f"Resumed {len(history)} previous messages.")

    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            display.info("Chat ended.")
            break

        if not user_input:
            continue

        # Slash commands
        if user_input.startswith("/"):
            cmd = user_input.lower()
            if cmd in ("/exit", "/quit", "/q"):
                display.info("Chat ended.")
                break
            elif cmd == "/history":
                for m in messages[-10:]:
                    role_fmt = "[bold cyan]You[/bold cyan]" if m["role"] == "user" else "[bold green]RageBot[/bold green]"
                    console.print(f"{role_fmt}: {m['content'][:120]}")
                continue
            elif cmd == "/clear":
                eng.db.delete_chat_session(sid)
                messages = []
                display.success("Session cleared.")
                continue
            elif cmd.startswith("/export"):
                parts = cmd.split()
                out   = parts[1] if len(parts) > 1 else f"chat_{sid}.json"
                Path(out).write_text(json.dumps(messages, indent=2))
                display.success(f"Chat exported to [bold]{out}[/bold]")
                continue
            else:
                display.warning(f"Unknown command: {user_input}")
                continue

        messages.append({"role": "user", "content": user_input})
        eng.db.save_chat_message(sid, "user", user_input)

        with _spin("Thinking…"):
            response = eng.chat(messages=messages, top_k=top_k)

        messages.append({"role": "assistant", "content": response})
        eng.db.save_chat_message(sid, "assistant", response)
        console.print(Panel(Markdown(response), title="[bold green]RageBot[/bold green]", border_style="green"))


# ═══════════════════════════════════════════════════════════════════════════════
# SEARCH
# ═══════════════════════════════════════════════════════════════════════════════
@app.command("search")
def cmd_search(
    query:       str = typer.Argument(..., help="Search query"),
    path:        str = typer.Option(".", "--path", "-p"),
    search_type: str = typer.Option("semantic", "--type", "-t", help="semantic|keyword|hybrid"),
    top_k:       int = typer.Option(10, "--top-k", "-k"),
    show_preview:bool= typer.Option(True, "--preview/--no-preview"),
):
    """🔎 Search project files (semantic, keyword, or hybrid)."""
    eng = _engine(path)
    with _spin(f"Searching [{search_type}]: {query!r}…"):
        results = eng.search(query=query, search_type=search_type, top_k=top_k)

    t = Table(title=f"🔎 Results for '{query}'  [{search_type}]", box=None, header_style="bold cyan")
    t.add_column("File",     style="cyan",   min_width=30)
    t.add_column("Score",    style="yellow", min_width=7)
    t.add_column("Preview",  style="white")
    for r in results:
        fp  = r.get("file") or r.get("file_path", "")
        sc  = r.get("score", 0.0)
        pre = r.get("preview", r.get("content", ""))[:100] if show_preview else ""
        t.add_row(fp, f"{sc:.3f}", pre)
    console.print(t)


# ═══════════════════════════════════════════════════════════════════════════════
# EXPLAIN
# ═══════════════════════════════════════════════════════════════════════════════
@app.command("explain")
def cmd_explain(
    file_path: str           = typer.Argument(..., help="Relative path to file"),
    symbol:    Optional[str] = typer.Option(None, "--symbol", "-s", help="Function or class name"),
    path:      str           = typer.Option(".", "--path", "-p"),
):
    """📖 Explain a source file or specific function/class."""
    eng = _engine(path)
    with _spin(f"Explaining {file_path}…"):
        result = eng.explain(file_path=file_path, symbol=symbol)

    if "error" in result:
        display.error(result["error"])
        raise typer.Exit(1)

    console.print(Panel(
        f"[bold]Functions:[/bold] {', '.join(result.get('functions',[]))  or 'none'}\n"
        f"[bold]Classes:[/bold]   {', '.join(result.get('classes',[]))    or 'none'}\n"
        f"[bold]Imports:[/bold]   {', '.join(result.get('imports',[])[:8]) or 'none'}",
        title=f"📄 {file_path}", border_style="cyan",
    ))
    console.print(Panel(Markdown(result.get("explanation", "")), title="💡 Explanation", border_style="green"))


# ═══════════════════════════════════════════════════════════════════════════════
# DOCS
# ═══════════════════════════════════════════════════════════════════════════════
@app.command("docs")
def cmd_docs(
    file_path: str           = typer.Argument(..., help="File to document"),
    path:      str           = typer.Option(".", "--path", "-p"),
    output:    Optional[str] = typer.Option(None, "--output", "-o", help="Save to .md file"),
):
    """📝 Generate Markdown documentation for a source file."""
    eng = _engine(path)
    with _spin(f"Generating docs for {file_path}…"):
        docs = eng.generate_docs(file_path)

    console.print(Panel(Markdown(docs), title=f"📝 Docs: {file_path}", border_style="cyan"))

    if output:
        Path(output).write_text(docs)
        display.success(f"Saved to [bold]{output}[/bold]")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════
@app.command("test")
def cmd_test(
    file_path: str           = typer.Argument(..., help="File to generate tests for"),
    path:      str           = typer.Option(".", "--path", "-p"),
    output:    Optional[str] = typer.Option(None, "--output", "-o"),
):
    """🧪 Generate pytest test cases for a source file."""
    eng = _engine(path)
    with _spin(f"Generating tests for {file_path}…"):
        tests = eng.generate_tests(file_path)

    console.print(Panel(
        Syntax(tests, "python", theme="monokai", line_numbers=True),
        title=f"🧪 Tests: {file_path}", border_style="cyan",
    ))

    if output:
        Path(output).write_text(tests)
        display.success(f"Saved to [bold]{output}[/bold]")


# ═══════════════════════════════════════════════════════════════════════════════
# DIFF
# ═══════════════════════════════════════════════════════════════════════════════
@app.command("diff")
def cmd_diff(
    diff_file: Optional[str] = typer.Argument(None, help="Path to diff file (or pipe via stdin)"),
    path:      str           = typer.Option(".", "--path", "-p"),
    staged:    bool          = typer.Option(False, "--staged", help="Explain staged git changes"),
    head:      bool          = typer.Option(False, "--head",   help="Explain HEAD~1 diff"),
):
    """🔀 Explain a git diff in plain English."""
    eng = _engine(path)

    diff_text = ""
    if staged:
        diff_text = subprocess.check_output(["git", "diff", "--staged"], cwd=path, text=True)
    elif head:
        diff_text = subprocess.check_output(["git", "diff", "HEAD~1"], cwd=path, text=True)
    elif diff_file:
        diff_text = Path(diff_file).read_text()
    elif not sys.stdin.isatty():
        diff_text = sys.stdin.read()
    else:
        display.error("Provide a diff file, use --staged, --head, or pipe diff via stdin.")
        raise typer.Exit(1)

    with _spin("Analysing diff…"):
        explanation = eng.diff_explain(diff_text)

    console.print(Panel(Markdown(explanation), title="🔀 Diff Explanation", border_style="cyan"))


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT
# ═══════════════════════════════════════════════════════════════════════════════
@app.command("context")
def cmd_context(
    path:    str           = typer.Argument(".", help="Project directory"),
    file:    Optional[str] = typer.Option(None, "--file", "-f"),
    summary: bool          = typer.Option(False, "--summary", "-s"),
    tree:    bool          = typer.Option(False, "--tree",    "-t"),
):
    """📋 Show project structure, summaries, or file-level context."""
    eng = _engine(path)
    if tree:
        result = eng.get_file_tree()
        console.print(Panel(result["tree"], title="🌳 Project Tree", border_style="cyan"))
    elif file:
        result = eng.get_file_context(file)
        if "error" in result:
            display.error(result["error"]); raise typer.Exit(1)
        console.print(Panel(
            f"[bold]Summary:[/bold]   {result.get('summary','')}\n"
            f"[bold]Type:[/bold]      {result.get('type','')}\n"
            f"[bold]Functions:[/bold] {', '.join(result.get('functions',[]))}\n"
            f"[bold]Classes:[/bold]   {', '.join(result.get('classes',[]))}\n"
            f"[bold]Imports:[/bold]   {', '.join(result.get('imports',[])[:10])}",
            title=f"📄 {file}", border_style="green",
        ))
    elif summary:
        with _spin("Generating project summary…"):
            result = eng.get_project_summary()
        console.print(Panel(Markdown(result["summary"]), title="📊 Project Summary", border_style="yellow"))
    else:
        result = eng.get_project_overview()
        t = Table(title="📊 Project Overview", box=None, header_style="bold cyan")
        t.add_column("Metric", style="cyan"); t.add_column("Value", style="green")
        for k, v in result.items():
            t.add_row(k.replace("_"," ").title(), str(v))
        console.print(t)


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════
@app.command("export")
def cmd_export(
    agent_type: str           = typer.Argument(..., help="debug|docs|refactor|review|test"),
    path:       str           = typer.Option(".", "--path", "-p"),
    output:     str           = typer.Option("./rage_context.json", "--output", "-o"),
    focus:      Optional[str] = typer.Option(None, "--focus", "-f"),
):
    """📦 Export an optimised context pack for a specific AI agent role."""
    eng = _engine(path)
    with _spin(f"Building [{agent_type}] context pack…"):
        result = eng.export_context(agent_type=agent_type, focus=focus)
    Path(output).write_text(json.dumps(result, indent=2))
    display.success(f"Exported to [bold]{output}[/bold]")
    display.info(f"Files: {result.get('file_count',0)}  •  Tokens: ~{result.get('token_count',0)}")


# ═══════════════════════════════════════════════════════════════════════════════
# SNAPSHOTS
# ═══════════════════════════════════════════════════════════════════════════════
snapshots_app = typer.Typer(help="📸 Manage project snapshots")
app.add_typer(snapshots_app, name="snapshots")


@snapshots_app.command("list")
def snap_list(path: str = typer.Argument(".", help="Project directory")):
    """List all saved snapshots."""
    eng = _engine(path)
    snaps = eng.list_snapshots()
    if not snaps:
        display.info("No snapshots found. Run [bold cyan]rage save --name <name>[/bold cyan].")
        return
    t = Table(title="📸 Snapshots", box=None, header_style="bold cyan")
    t.add_column("Name",    style="cyan"); t.add_column("Created",  style="green")
    t.add_column("Files",   style="yellow"); t.add_column("Size", style="magenta")
    for s in snaps:
        t.add_row(s["name"], s["created"], str(s["files"]), s["size"])
    console.print(t)


@snapshots_app.command("restore")
def snap_restore(
    name: str = typer.Argument(..., help="Snapshot name"),
    path: str = typer.Option(".", "--path", "-p"),
):
    """Restore a snapshot."""
    eng = _engine(path)
    eng.restore_snapshot(name)
    display.success(f"Snapshot [bold]{name}[/bold] restored.")


@snapshots_app.command("delete")
def snap_delete(
    name: str = typer.Argument(..., help="Snapshot name"),
    path: str = typer.Option(".", "--path", "-p"),
):
    """Delete a snapshot."""
    eng  = _engine(path)
    confirm = typer.confirm(f"Delete snapshot '{name}'?")
    if not confirm: raise typer.Abort()
    eng.delete_snapshot(name)
    display.success(f"Snapshot [bold]{name}[/bold] deleted.")


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS
# ═══════════════════════════════════════════════════════════════════════════════
@app.command("status")
def cmd_status(path: str = typer.Argument(".", help="Project directory")):
    """📡 Show index status and LLM health."""
    eng = _engine(path)
    s = eng.get_status()
    llm_status = "[bold green]✓ Ready[/bold green]" if s.get("llm_ready") else "[bold red]✗ Not configured[/bold red]"
    console.print(Panel(
        f"[cyan]Project:[/cyan]          {s.get('project_path')}\n"
        f"[cyan]Indexed Files:[/cyan]    {s.get('indexed_files')}\n"
        f"[cyan]Last Saved:[/cyan]       {s.get('last_saved','Never')}\n"
        f"[cyan]Modified Since:[/cyan]   {s.get('modified_since',0)} file(s)\n"
        f"[cyan]Snapshots:[/cyan]        {s.get('snapshot_count',0)}\n"
        f"[cyan]DB Size:[/cyan]          {s.get('db_size','N/A')}\n"
        f"[cyan]Embedding Model:[/cyan]  {s.get('embedding_model','N/A')}\n"
        f"[cyan]LLM Provider:[/cyan]     {s.get('llm_provider','N/A')}  {llm_status}",
        title="📡 RageBot Status", border_style="blue",
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# WATCH
# ═══════════════════════════════════════════════════════════════════════════════
@app.command("watch")
def cmd_watch(
    path:     str = typer.Argument(".", help="Project directory"),
    debounce: int = typer.Option(3, "--debounce", "-d"),
):
    """👁️  Watch for file changes and auto re-index."""
    from ragebot.core.watcher import FileWatcher
    eng = _engine(path)
    display.info(f"Watching [bold]{path}[/bold]  (Ctrl+C to stop)")
    FileWatcher(engine=eng, debounce=debounce).start()


# ═══════════════════════════════════════════════════════════════════════════════
# CLEAN
# ═══════════════════════════════════════════════════════════════════════════════
@app.command("clean")
def cmd_clean(
    path:     str  = typer.Argument(".", help="Project directory"),
    all_data: bool = typer.Option(False, "--all", "-a", help="Remove ALL RageBot data"),
):
    """🧹 Clean cache and/or index data."""
    if all_data:
        typer.confirm("⚠️  Delete ALL RageBot data for this project?", abort=True)
    _engine(path).clean(all_data=all_data)
    display.success("Clean complete.")


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH  (secure API key management)
# ═══════════════════════════════════════════════════════════════════════════════
auth_app = typer.Typer(help="🔐 Manage API keys (stored securely in OS keyring)")
app.add_typer(auth_app, name="auth")


@auth_app.command("login")
def auth_login(
    provider: str = typer.Argument(..., help="Provider: gemini | grok"),
    key:      Optional[str] = typer.Option(None, "--key", "-k", help="API key (prompted if omitted)"),
):
    """Store an API key securely in the OS keyring."""
    provider = provider.lower()
    valid = {"gemini", "grok"}
    if provider not in valid:
        display.error(f"Unknown provider: {provider}. Choose from: {', '.join(valid)}")
        raise typer.Exit(1)

    if not key:
        import getpass
        key = getpass.getpass(f"Enter {provider.title()} API key: ").strip()

    if not key:
        display.error("No key provided.")
        raise typer.Exit(1)

    cfg    = ConfigManager()
    secret_key = f"{provider}_api_key"
    result = cfg.set(secret_key, key)

    if result["stored"] == "keyring":
        display.success(f"[bold]{provider.title()}[/bold] API key stored securely in OS keyring 🔒")
    elif result["stored"] == "file":
        display.success(f"[bold]{provider.title()}[/bold] API key stored in [dim]~/.config/ragebot/.secrets[/dim] (chmod 600) 🔒")
        display.info("For stronger security, install a keyring backend: [bold]pip install keyring[/bold]")
    else:
        display.warning("Key storage uncertain — check your keyring setup.")
    # Set the default provider regardless
    cfg.set("llm_provider", provider)
    display.info(f"Default LLM provider set to [bold cyan]{provider}[/bold cyan]")


@auth_app.command("logout")
def auth_logout(provider: str = typer.Argument(..., help="Provider: gemini | grok")):
    """Remove an API key from the OS keyring."""
    provider = provider.lower()
    cfg = ConfigManager()
    ok  = cfg.delete_secret(f"{provider}_api_key")
    if ok:
        display.success(f"[bold]{provider.title()}[/bold] API key removed.")
    else:
        display.warning("Could not remove key (keyring unavailable or key not found).")


@auth_app.command("status")
def auth_status():
    """Show which providers are authenticated."""
    cfg = ConfigManager()
    t = Table(title="🔐 Auth Status", box=None, header_style="bold cyan")
    t.add_column("Provider", style="cyan")
    t.add_column("Status",   style="green")
    t.add_column("Model",    style="yellow")
    for provider in ("gemini", "grok"):
        key   = cfg.get(f"{provider}_api_key", "")
        model_key = f"{provider}_model"
        model = cfg.get(model_key, "")
        if key:
            t.add_row(provider.title(), "✓ Authenticated", model)
        else:
            t.add_row(provider.title(), "[red]✗ Not set[/red]", model)
    console.print(t)


@auth_app.command("switch")
def auth_switch(provider: str = typer.Argument(..., help="gemini | grok")):
    """Switch the active LLM provider."""
    provider = provider.lower()
    if provider not in ("gemini", "grok", "none"):
        display.error("Choose: gemini | grok | none"); raise typer.Exit(1)
    cfg = ConfigManager()
    cfg.set("llm_provider", provider)
    display.success(f"Active provider → [bold cyan]{provider}[/bold cyan]")


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
config_app = typer.Typer(help="⚙️  Manage non-secret configuration")
app.add_typer(config_app, name="config")


@config_app.command("show")
def cfg_show():
    """Show all current configuration values."""
    cfg = ConfigManager()
    t = Table(title="⚙️  Configuration  [dim](~/.config/ragebot/config.json)[/dim]",
              box=None, header_style="bold cyan")
    t.add_column("Key",   style="cyan",  min_width=24)
    t.add_column("Value", style="green")
    for k, v in cfg.get_all().items():
        t.add_row(k, str(v))
    console.print(t)


@config_app.command("set")
def cfg_set(
    key:   str = typer.Argument(...),
    value: str = typer.Argument(...),
):
    """Set a configuration value (non-secret). For API keys use `rage auth login`."""
    cfg = ConfigManager()
    if key in cfg.secret_keys:
        display.warning(f"[bold]{key}[/bold] is a secret. Use [bold cyan]rage auth login[/bold cyan] instead.")
        raise typer.Exit(1)
    cfg.set(key, value)
    display.success(f"Set [bold]{key}[/bold] = [bold]{value}[/bold]")


@config_app.command("get")
def cfg_get(key: str = typer.Argument(...)):
    """Get a single configuration value."""
    cfg = ConfigManager()
    val = cfg.get(key)
    if val is None:
        display.error(f"Key not found: {key}"); raise typer.Exit(1)
    console.print(f"[cyan]{key}[/cyan] = [green]{val}[/green]")


@config_app.command("reset")
def cfg_reset():
    """Reset all non-secret configuration to defaults."""
    typer.confirm("Reset all config to defaults?", abort=True)
    ConfigManager().reset()
    display.success("Configuration reset.")


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT HISTORY
# ═══════════════════════════════════════════════════════════════════════════════
history_app = typer.Typer(help="🗂  Manage chat history sessions")
app.add_typer(history_app, name="history")


@history_app.command("list")
def hist_list(path: str = typer.Argument(".", help="Project directory")):
    """List all chat sessions."""
    eng = _engine(path)
    sessions = eng.db.list_chat_sessions()
    if not sessions:
        display.info("No chat history found."); return
    t = Table(title="🗂  Chat Sessions", box=None, header_style="bold cyan")
    t.add_column("Session ID", style="cyan"); t.add_column("Started", style="green")
    t.add_column("Last Msg",   style="yellow"); t.add_column("Messages", style="magenta")
    for s in sessions:
        fmt = lambda ts: time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else ""
        t.add_row(s["session_id"], fmt(s["started"]), fmt(s["last_msg"]), str(s["messages"]))
    console.print(t)


@history_app.command("show")
def hist_show(
    session_id: str = typer.Argument(...),
    path:       str = typer.Option(".", "--path", "-p"),
    limit:      int = typer.Option(20, "--limit", "-n"),
):
    """Show messages from a chat session."""
    eng = _engine(path)
    msgs = eng.db.get_chat_history(session_id, limit=limit)
    for m in msgs:
        role = "[bold cyan]You[/bold cyan]" if m["role"] == "user" else "[bold green]RageBot[/bold green]"
        console.print(f"{role}: {m['content']}\n")


@history_app.command("delete")
def hist_delete(
    session_id: str = typer.Argument(...),
    path:       str = typer.Option(".", "--path", "-p"),
):
    """Delete a chat session."""
    typer.confirm(f"Delete session '{session_id}'?", abort=True)
    _engine(path).db.delete_chat_session(session_id)
    display.success(f"Session [bold]{session_id}[/bold] deleted.")


# ═══════════════════════════════════════════════════════════════════════════════
# MCP SERVER
# ═══════════════════════════════════════════════════════════════════════════════
mcp_app = typer.Typer(help="🔌 MCP server management")
app.add_typer(mcp_app, name="mcp")


@mcp_app.command("start")
def mcp_start(
    path:      str = typer.Option(".", "--path", "-p", help="Project directory"),
    transport: str = typer.Option("stdio", "--transport", "-t", help="stdio | sse"),
    host:      str = typer.Option("127.0.0.1", "--host"),
    port:      int = typer.Option(8765,       "--port"),
    log_level: str = typer.Option("WARNING",  "--log-level"),
):
    """Start the MCP server (stdio or SSE transport)."""
    from ragebot.mcp.server import RageBotMCPServer, run_stdio, run_sse

    cfg    = ConfigManager()
    eng_p  = Path(path).resolve()
    server = RageBotMCPServer(project_path=eng_p, config=cfg)

    if not (eng_p / ".ragebot" / "ragebot.db").exists():
        display.info("Project not indexed — running init…")
        server.engine.initialize()

    if transport == "sse":
        display.info(f"Starting MCP SSE server on [bold]http://{host}:{port}[/bold]")
        run_sse(server, host=host, port=port)
    else:
        display.info("Starting MCP stdio server…")
        run_stdio(server)


@mcp_app.command("config")
def mcp_config_cmd(
    transport: Optional[str] = typer.Option(None, "--transport", "-t"),
    host:      Optional[str] = typer.Option(None, "--host"),
    port:      Optional[int] = typer.Option(None, "--port"),
):
    """Configure MCP server defaults."""
    cfg = ConfigManager()
    if transport: cfg.set("mcp_transport", transport)
    if host:      cfg.set("mcp_host",      host)
    if port:      cfg.set("mcp_port",      str(port))
    display.success("MCP config updated.")
    t = Table(box=None, header_style="bold cyan")
    t.add_column("Setting"); t.add_column("Value")
    t.add_row("transport", cfg.get("mcp_transport")); t.add_row("host", cfg.get("mcp_host"))
    t.add_row("port",      cfg.get("mcp_port"))
    console.print(t)


# ═══════════════════════════════════════════════════════════════════════════════
# VERSION
# ═══════════════════════════════════════════════════════════════════════════════
@app.command("version")
def cmd_version():
    """Show RageBot version information."""
    cfg = ConfigManager()
    console.print(Panel(
        "[bold cyan]RageBot MCP[/bold cyan]  v1.0.0\n"
        "Intelligent Project Context Engine with MCP support\n\n"
        f"[dim]LLM Provider:     {cfg.get('llm_provider','none')}[/dim]\n"
        f"[dim]Embedding Model:  {cfg.get('embedding_model','N/A')}[/dim]\n"
        "[dim]github.com/ragebot/mcp[/dim]",
        border_style="cyan",
    ))


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    app()


if __name__ == "__main__":
    main()
