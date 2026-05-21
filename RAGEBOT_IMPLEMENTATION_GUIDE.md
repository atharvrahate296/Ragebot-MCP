# RageBot MCP — Implementation Guide
### Advanced Error Handling · Enhanced Logging · REPL Command Fix · UI/UX Overhaul

---

## Table of Contents

1. [Critical Bug Fix — REPL Command Arguments](#1-critical-bug-fix--repl-command-arguments)
2. [Advanced Error Handling Integration](#2-advanced-error-handling-integration)
3. [Enhanced Logging Integration](#3-enhanced-logging-integration)
4. [UI / Display / UX Overhaul](#4-ui--display--ux-overhaul)
5. [Full File-by-File Change Breakdown](#5-full-file-by-file-change-breakdown)
6. [Testing Checklist](#6-testing-checklist)

---

## 1. Critical Bug Fix — REPL Command Arguments

### Root Cause

The error:
```
argument should be a str or an os.PathLike object where __fspath__ returns a str, not 'OptionInfo'
```

occurs because the REPL command handlers in `_run_interactive_repl()` and the `cmd_chat()` handler call the Typer command functions **directly** (`cmd_explain(file_path=fp)`), passing plain Python strings. Typer decorates each parameter with `typer.Option(...)` or `typer.Argument(...)`, which wraps them in `OptionInfo` / `ArgumentInfo` objects. When Typer is NOT parsing a real CLI invocation those wrappers do not resolve to plain values — the function receives an `OptionInfo` object instead of a string.

### Fix Strategy

**Never call `cmd_*` functions directly from the REPL.** Extract all real logic into plain helper functions (no Typer decorators) and have both the Typer-decorated command AND the REPL call the helper.

### Implementation

#### Step 1 — Create `ragebot/core/commands.py` (new file)

This file contains every action as a plain Python function with no Typer dependency.

```python
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
from ragebot.utils.ui_helpers import (
    show_friendly_error, show_success_badge,
    show_warning_badge, show_info_badge,
)

console = Console()


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
    except Exception as e:
        show_friendly_error(console, "Initialization Error", str(e))


# ── save ─────────────────────────────────────────────────────────────────────

def do_save(path: str = ".", incremental: bool = True,
            snapshot_name: Optional[str] = None) -> None:
    """Index project and save snapshot."""
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Prompt
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

        with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}"),
                      transient=True) as p:
            p.add_task("Indexing project…", total=None)
            result = eng.save(incremental=incremental, snapshot_name=snapshot_name)

        t = Table(title="📊 Indexing Summary", box=None, header_style="bold cyan")
        t.add_column("Metric", style="cyan", min_width=20)
        t.add_column("Value",  style="green")
        t.add_row("Snapshot Name",    result["snapshot_name"])
        t.add_row("Files Indexed",    str(result["indexed"]))
        t.add_row("Files Skipped",    str(result["skipped"]))
        t.add_row("Tokens Estimated", str(result["token_estimate"]))
        t.add_row("Timestamp",        time.strftime("%Y-%m-%d %H:%M:%S"))
        console.print(t)
    except Exception as e:
        show_friendly_error(console, "Save Error", str(e))


# ── ask ──────────────────────────────────────────────────────────────────────

def do_ask(query: str, path: str = ".", mode: str = "smart",
           top_k: int = 5, show_files: bool = True,
           export: Optional[str] = None) -> None:
    """Single-turn AI question."""
    from rich.progress import Progress, SpinnerColumn, TextColumn
    try:
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
    except Exception as e:
        show_friendly_error(console, "Ask Error", str(e))


# ── explain ──────────────────────────────────────────────────────────────────

def do_explain(file_path: str, symbol: Optional[str] = None,
               path: str = ".") -> None:
    """Explain a file or symbol."""
    from rich.progress import Progress, SpinnerColumn, TextColumn
    try:
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
    except Exception as e:
        show_friendly_error(console, "Explain Error", str(e))


# ── docs ─────────────────────────────────────────────────────────────────────

def do_docs(file_path: str, path: str = ".",
            output: Optional[str] = None) -> None:
    """Generate Markdown documentation for a file."""
    from rich.progress import Progress, SpinnerColumn, TextColumn
    try:
        eng = _engine(path)
        with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}"),
                      transient=True) as p:
            p.add_task("Generating docs…", total=None)
            docs = eng.generate_docs(file_path)
        console.print(Panel(Markdown(docs), border_style="cyan"))
        if output:
            Path(output).write_text(docs)
            show_success_badge(console, f"Saved to [bold]{output}[/bold]")
    except Exception as e:
        show_friendly_error(console, "Docs Error", str(e))


# ── test ─────────────────────────────────────────────────────────────────────

def do_test(file_path: str, path: str = ".",
            output: Optional[str] = None) -> None:
    """Generate pytest tests for a file."""
    from rich.progress import Progress, SpinnerColumn, TextColumn
    try:
        eng = _engine(path)
        with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}"),
                      transient=True) as p:
            p.add_task("Generating tests…", total=None)
            tests = eng.generate_tests(file_path)
        console.print(Panel(Syntax(tests, "python"), border_style="cyan"))
        if output:
            Path(output).write_text(tests)
            show_success_badge(console, f"Saved to [bold]{output}[/bold]")
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
    except Exception as e:
        show_friendly_error(console, "Search Error", str(e))


# ── status ───────────────────────────────────────────────────────────────────

def do_status(path: str = ".") -> None:
    """Show index status."""
    try:
        eng = _engine(path)
        if not (eng.rage_dir / "ragebot.db").exists():
            show_warning_badge(console, f"Project at {path} is not initialized.")
            return
        s = eng.get_status()
        llm_status = (
            "[bold green]✓ Ready[/bold green]"
            if s.get("llm_ready")
            else "[bold red]✗ Not configured[/bold red]"
        )
        console.print(Panel(
            f"[cyan]Project:[/cyan]          {s.get('project_path')}\n"
            f"[cyan]Indexed Files:[/cyan]    {s.get('indexed_files')}\n"
            f"[cyan]Last Saved:[/cyan]       {s.get('last_saved','Never')}\n"
            f"[cyan]LLM Provider:[/cyan]     {s.get('llm_provider','N/A')}  {llm_status}",
            title="📡 RageBot Status", border_style="blue",
        ))
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
```

#### Step 2 — Rewrite `_run_interactive_repl()` in `ragebot/cli.py`

Replace every `cmd_*()` direct call inside `_run_interactive_repl()` with the corresponding `do_*()` helper. The key changes are shown below (only the REPL body needs updating — the Typer `@app.command` wrappers stay unchanged):

```python
# ragebot/cli.py  — inside _run_interactive_repl()
# ADD at top of file:
from ragebot.core.commands import (
    do_init, do_save, do_ask, do_explain, do_docs,
    do_test, do_search, do_status, do_context, do_snapshot,
)

# REPLACE direct cmd_* calls:

# OLD  →  cmd_status(path=p)
# NEW  →  do_status(path=p)

# OLD  →  cmd_save(path=p)
# NEW  →  do_save(path=p)

# OLD  →  cmd_init(path=p)
# NEW  →  do_init(path=p)

# OLD  →  cmd_search(query=query)
# NEW  →  do_search(query=query)

# OLD  →  cmd_explain(file_path=fp)
# NEW  →  do_explain(file_path=fp)

# OLD  →  cmd_docs(file_path=fp)
# NEW  →  do_docs(file_path=fp)

# OLD  →  cmd_test(file_path=fp)
# NEW  →  do_test(file_path=fp)

# OLD  →  cmd_context(path=p)
# NEW  →  do_context(path=p)

# OLD  →  cmd_snapshot(action=action, name=snap_name)
# NEW  →  do_snapshot(action=action, name=snap_name)
```

#### Step 3 — Rewrite Typer command wrappers to use helpers

Each `@app.command` now becomes a thin wrapper:

```python
# ragebot/cli.py

@app.command("explain")
def cmd_explain(
    file_path: str = typer.Argument(...),
    symbol: Optional[str] = typer.Option(None, "--symbol", "-s"),
    path: str = typer.Option("."),
):
    """📖 Explain code."""
    do_explain(file_path=file_path, symbol=symbol, path=path)


@app.command("docs")
def cmd_docs(
    file_path: str = typer.Argument(...),
    path: str = typer.Option("."),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
):
    """📝 Generate docs."""
    do_docs(file_path=file_path, path=path, output=output)


@app.command("test")
def cmd_test(
    file_path: str = typer.Argument(...),
    path: str = typer.Option("."),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
):
    """🧪 Generate tests."""
    do_test(file_path=file_path, path=path, output=output)


@app.command("search")
def cmd_search(
    query: str = typer.Argument(...),
    path: str = typer.Option(".", "--path", "-p"),
    search_type: str = typer.Option("semantic", "--type", "-t"),
    top_k: int = typer.Option(10, "--top-k", "-k"),
):
    """🔎 Semantic search."""
    do_search(query=query, path=path, search_type=search_type, top_k=top_k)


@app.command("init")
def cmd_init(
    path: str = typer.Argument("."),
    force: bool = typer.Option(False, "--force", "-f"),
):
    """🚀 Initialize RageBot."""
    do_init(path=path, force=force)


@app.command("save")
def cmd_save(
    path: str = typer.Argument("."),
    incremental: bool = typer.Option(True, "--incremental/--full"),
    snapshot_name: Optional[str] = typer.Option(None, "--name", "-n"),
):
    """💾 Index project and save snapshot."""
    do_save(path=path, incremental=incremental, snapshot_name=snapshot_name)
```

---

## 2. Advanced Error Handling Integration

The `ragebot/utils/error_handler.py` already exists with all classes. The following covers **where** and **how** to wire it into the rest of the codebase.

### 2.1 — `ragebot/core/engine.py`

Wrap LLM calls and indexing loops with typed errors:

```python
# ragebot/core/engine.py — imports section
from ragebot.utils.error_handler import (
    ErrorHandler, ErrorCategory, ErrorSeverity, RageBotError
)

_error_handler = ErrorHandler()
```

**In `save()` — replace bare `except Exception`:**

```python
# BEFORE:
except Exception:
    skipped += 1

# AFTER:
except Exception as exc:
    skipped += 1
    _error_handler.handle_error(
        exc, context=f"Indexing {rel}"
    )
```

**In `ask()` / `chat()` — wrap provider call:**

```python
# In _generate_answer():
try:
    return provider.complete(
        _SYSTEM_PROMPT, user_prompt,
        max_tokens=self.config.get_int("max_answer_tokens", 1000),
    )
except Exception as exc:
    msg = str(exc)
    if "rate" in msg.lower() or "429" in msg:
        raise RageBotError(
            "Rate limit reached",
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.WARNING,
            recovery_steps=[
                "Wait 60 seconds and retry",
                "Switch to a different model: rage model",
                "Switch provider: rage auth",
            ],
            context={"provider": provider.name},
        )
    elif "auth" in msg.lower() or "401" in msg or "403" in msg:
        raise RageBotError(
            "Authentication failed",
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.ERROR,
            recovery_steps=[
                f"Re-authenticate: rage auth login <provider>",
                "Check your API key is valid",
            ],
        )
    raise
```

### 2.2 — `ragebot/llm/gemini.py`

Replace internal error strings with `RageBotError` raises so callers can catch typed errors:

```python
# ragebot/llm/gemini.py — in complete()
from ragebot.utils.error_handler import RageBotError, ErrorCategory, ErrorSeverity

# In _handle_api_error(), instead of returning long strings, raise:
if error.code == 429:
    raise RageBotError(
        "Gemini rate limit exceeded",
        category=ErrorCategory.RATE_LIMIT,
        severity=ErrorSeverity.WARNING,
        recovery_steps=[
            "Wait a few minutes and retry",
            "Upgrade quota at https://aistudio.google.com/app/apikey",
            "Switch to gemini-1.5-flash (higher rate limits)",
        ],
        context={"provider": "gemini", "model": self._model},
    )
if error.code in (401, 403):
    raise RageBotError(
        "Gemini authentication failed",
        category=ErrorCategory.AUTHENTICATION,
        severity=ErrorSeverity.ERROR,
        recovery_steps=[
            "Run: rage auth login gemini",
            "Verify key at https://aistudio.google.com/app/apikey",
        ],
    )
```

### 2.3 — `ragebot/llm/groq.py`

Same pattern — replace `return "[Groq error: ...]"` strings with raises:

```python
# ragebot/llm/groq.py — in complete()
from ragebot.utils.error_handler import RageBotError, ErrorCategory, ErrorSeverity

except Exception as exc:
    msg = str(exc)
    if "rate_limit" in msg.lower() or "429" in msg:
        raise RageBotError(
            "Groq rate limit exceeded",
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.WARNING,
            recovery_steps=[
                "Wait a moment and retry",
                "Switch to a smaller model: rage model",
            ],
            context={"provider": "groq", "model": self._model},
        )
    if "401" in msg or "auth" in msg.lower():
        raise RageBotError(
            "Groq authentication failed",
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.ERROR,
            recovery_steps=["Run: rage auth login groq"],
        )
    raise RageBotError(
        f"Groq API error: {exc}",
        category=ErrorCategory.PROVIDER_FAILURE,
        severity=ErrorSeverity.ERROR,
    )
```

### 2.4 — `ragebot/storage/snapshot.py`

```python
# ragebot/storage/snapshot.py — in restore()
from ragebot.utils.error_handler import RageBotError, ErrorCategory, ErrorSeverity

if not snap_db.exists():
    raise RageBotError(
        f"Snapshot '{name}' database file is missing",
        category=ErrorCategory.SNAPSHOT,
        severity=ErrorSeverity.ERROR,
        recovery_steps=[
            "List available snapshots: rage snapshot list",
            "Create a fresh snapshot: rage save",
        ],
        context={"snapshot_name": name},
    )
```

### 2.5 — `ragebot/core/commands.py` (the new file)

Catch `RageBotError` specifically before the generic `Exception` catch:

```python
# In each do_*() function:
from ragebot.utils.error_handler import RageBotError, ErrorHandler

_err = ErrorHandler(console)

try:
    # ... operation ...
except RageBotError as e:
    _err.handle_error(e)
except Exception as e:
    _err.handle_error(e, context="Performing explain")
```

---

## 3. Enhanced Logging Integration

`ragebot/utils/logging_config.py` already has `BackgroundTaskLogger` and `ProgressState`. Below is the integration wiring.

### 3.1 — `ragebot/cli.py` startup

`suppress_noisy_logs()` is already called. Also add:

```python
# ragebot/cli.py — top of file, after existing import
from ragebot.utils.logging_config import BackgroundTaskLogger, ProgressState
```

### 3.2 — `ragebot/core/engine.py` — `save()` method

Replace the plain `print`/pass pattern with `ProgressState`:

```python
# ragebot/core/engine.py — in save()
from ragebot.utils.logging_config import BackgroundTaskLogger, ProgressState

def save(self, incremental: bool = True,
         snapshot_name: Optional[str] = None) -> dict:
    self.rage_dir.mkdir(parents=True, exist_ok=True)
    self.db.init_schema()

    scanner   = DirectoryScanner(self.project_path, self.config)
    all_files = scanner.scan()

    # NEW: set up progress tracking
    task_log  = BackgroundTaskLogger("save")
    progress  = ProgressState("indexing", total_items=len(all_files))

    code_parser = CodeParser()
    doc_parser  = DocumentParser()

    indexed = skipped = total_tokens = 0

    for i, file_path in enumerate(all_files):
        rel   = str(file_path.relative_to(self.project_path))
        fhash = self._hash_file(file_path)

        progress.update(i + 1, f"processing {file_path.name}")
        task_log.debug(f"Processing {rel}")

        if incremental and self.db.is_indexed(rel, fhash):
            skipped += 1
            continue

        try:
            # ... existing parse/embed/upsert logic ...
            indexed += 1
        except Exception as exc:
            skipped += 1
            progress.add_error(f"{rel}: {exc}")
            task_log.warning(f"Skipped {rel}: {exc}")

    progress.complete()
    summary = progress.get_summary()
    task_log.info(
        f"Save complete: {summary['processed']} processed, "
        f"{summary['errors']} errors"
    )

    # ... rest of save() unchanged ...
```

### 3.3 — `ragebot/search/embedder.py` — model loading

```python
# ragebot/search/embedder.py — in _load_model()
from ragebot.utils.logging_config import BackgroundTaskLogger

_emb_log = BackgroundTaskLogger("embedder")

def _load_model(self):
    if self._tried_import:
        return self._model
    self._tried_import = True
    _emb_log.info(f"Loading embedding model: {self.model_name}")
    try:
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self.model_name)
        _emb_log.info("Embedding model loaded successfully")
        return self._model
    except (ImportError, Exception) as e:
        _emb_log.warning(f"Failed to load model, using fallback: {e}")
        self._model = None
        return None
```

### 3.4 — `ragebot/llm/ollama.py` — model discovery

```python
# ragebot/llm/ollama.py — in _discover_models()
from ragebot.utils.logging_config import BackgroundTaskLogger

_ollama_log = BackgroundTaskLogger("ollama")

def _discover_models(self) -> None:
    _ollama_log.info(f"Discovering models from {self.base_url}/api/tags")
    try:
        # ... existing requests.get logic ...
        _ollama_log.info(f"Discovered {len(self.MODELS)} models")
    except requests.ConnectionError as e:
        _ollama_log.error(f"Cannot connect to Ollama at {self.base_url}")
        raise RuntimeError(f"Ollama server not running at {self.base_url}") from e
```

### 3.5 — Debug mode toggle (add to `rage config` command)

```python
# In ragebot/cli.py — inside cmd_config():
from ragebot.utils.logging_config import setup_debug_logging

@app.command("debug")
def cmd_debug(
    enable: bool = typer.Option(True, "--on/--off", help="Toggle debug logging"),
):
    """🐛 Toggle debug logging."""
    setup_debug_logging(enable=enable)
    state = "[green]enabled[/green]" if enable else "[yellow]disabled[/yellow]"
    show_info_badge(console, f"Debug logging {state}")
```

---

## 4. UI / Display / UX Overhaul

### 4.1 — Persistent Provider/Model Status Bar

Create `ragebot/utils/status_bar.py`:

```python
# ragebot/utils/status_bar.py
"""
StatusBar — renders a persistent provider/model/connection badge
that can be printed at the start of any AI-powered command output.
"""
from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
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
```

**Usage — add to the top of each AI command output:**

```python
# In do_ask(), do_explain(), do_docs(), do_test(), cmd_chat() — first line:
from ragebot.utils.status_bar import render_status_bar
render_status_bar(ConfigManager(), console)
```

### 4.2 — Interactive REPL Improvements

Replace the plain `Prompt.ask` input in `_run_interactive_repl()` with a `prompt_toolkit`-powered input that supports history and multi-line:

```python
# ragebot/cli.py — in _run_interactive_repl()
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.styles import Style

    pt_style  = Style.from_dict({"prompt": "bold ansicyan"})
    pt_session = PromptSession(
        history=InMemoryHistory(),
        auto_suggest=AutoSuggestFromHistory(),
        style=pt_style,
    )

    def _get_input() -> str:
        return pt_session.prompt("❯ ").strip()

except ImportError:
    def _get_input() -> str:
        from rich.prompt import Prompt
        return Prompt.ask("[bold cyan]❯[/bold cyan]").strip()
```

Replace the `raw_input = Prompt.ask(...)` line in the loop with `raw_input = _get_input()`.

### 4.3 — Buffered Streaming Response Rendering

For long AI responses in chat, render incrementally using a Live display:

```python
# ragebot/cli.py — in _run_interactive_repl() and cmd_chat()
# Replace the _spin("Thinking…") + console.print(Panel(Markdown(...))) block:

from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

# Show spinner while waiting, then render final markdown
with Live(
    Spinner("dots", text="[bold cyan]Thinking…[/bold cyan]"),
    refresh_per_second=12,
    transient=True,
) as live:
    response = eng.chat(messages=messages, top_k=5, session_id=session_id)

console.print(Panel(
    Markdown(response),
    title="[bold green]Ragebot[/bold green]",
    border_style="green",
    subtitle=f"[dim]{len(response.split())} words[/dim]",
    subtitle_align="right",
))
```

### 4.4 — Auth UX — Connection Feedback & Provider Switch Prompt

Add to `ragebot/auth/provider_auth.py` — replace the bare print in test connection:

```python
# ragebot/auth/provider_auth.py — in _auth_gemini() and _auth_groq()
# Replace the "Testing connection..." print:

from rich.live import Live
from rich.spinner import Spinner

self.console.print()
with Live(
    Spinner("dots", text=f"[cyan]Testing {provider} connection…[/cyan]"),
    refresh_per_second=10,
    transient=True,
):
    success, msg = self.provider_mgr.test_provider_connection()

if success:
    self.console.print(
        Panel(
            f"[bold green]✓  Connected to {provider.title()}[/bold green]",
            border_style="green", padding=(0, 2), expand=False,
        )
    )
else:
    self.console.print(
        Panel(
            f"[bold red]✗  Connection failed[/bold red]\n"
            f"[dim]{msg}[/dim]\n\n"
            f"[yellow]💡 Check your key or network, then retry:[/yellow]\n"
            f"  rage auth login {provider}",
            border_style="red", padding=(1, 2),
        )
    )
```

**Rate-limit prompt in chat:**

```python
# ragebot/core/commands.py — inside do_ask() and do_explain()
# In the except RageBotError block, if category is RATE_LIMIT:

from ragebot.utils.error_handler import RageBotError, ErrorCategory
import questionary

except RageBotError as e:
    _err.handle_error(e)
    if e.category == ErrorCategory.RATE_LIMIT:
        switch = questionary.confirm(
            "Switch to a different provider now?",
            default=False,
        ).ask()
        if switch:
            from ragebot.cli import _do_switch_interactive
            _do_switch_interactive()
```

### 4.5 — Improved Search Result Display

Add to `ragebot/utils/search_formatter.py` — richer result cards:

```python
# ragebot/utils/search_formatter.py — replace format_results()
def format_results(self, results, query="", max_preview_length=150):
    if not results:
        self.console.print(
            Panel("[yellow]No results found.[/yellow]",
                  border_style="yellow", expand=False)
        )
        return

    if query:
        self.console.print(
            Panel(f"[bold cyan]🔍 {query}[/bold cyan]  "
                  f"[dim]→ {len(results)} result(s)[/dim]",
                  border_style="cyan", padding=(0, 2), expand=False)
        )

    for i, r in enumerate(results[:20], 1):
        file_path = r.get("file_path") or r.get("file", "?")
        score     = r.get("score", 0)
        ftype     = r.get("file_type", "")
        content   = r.get("content", r.get("preview", ""))

        # Score bar (0-1 → 10 chars)
        bar_len  = max(1, int(score * 10)) if isinstance(score, float) else 0
        bar      = "█" * bar_len + "░" * (10 - bar_len)
        score_str = f"[green]{bar}[/green] {score:.3f}" if isinstance(score, float) else str(score)

        preview = self._create_preview(content, max_preview_length)

        self.console.print(
            Panel(
                f"[dim]{score_str}[/dim]\n{preview}",
                title=f"[bold cyan]{i}.[/bold cyan] [yellow]{file_path}[/yellow]  [dim]{ftype}[/dim]",
                border_style="blue",
                padding=(0, 2),
                expand=False,
            )
        )
```

### 4.6 — Snapshot & History Displays

Add rich table headers and active-state markers (already partially in place). Ensure these use the new `do_snapshot()` helper everywhere.

**Session list improvements — add preview column:**

In `ragebot/storage/session_manager.py` the `display_sessions_interactive()` already shows preview. Add a timestamp delta:

```python
# In display_sessions_interactive() — replace the started column:
import time as _time
now = _time.time()
delta = now - sess["last_msg"]
if delta < 3600:
    age = f"{int(delta/60)}m ago"
elif delta < 86400:
    age = f"{int(delta/3600)}h ago"
else:
    age = f"{int(delta/86400)}d ago"
# Use age instead of raw timestamp in the table row
```

### 4.7 — Bottom-Right Error Notifications

For async/background errors (e.g. watcher reindex failures) add a notification bar:

```python
# ragebot/utils/ui_helpers.py — add at the bottom:

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
```

---

## 5. Full File-by-File Change Breakdown

| File | Change Type | Summary |
|---|---|---|
| `ragebot/core/commands.py` | **NEW** | All plain-Python command helpers (fixes REPL bug) |
| `ragebot/cli.py` | **MODIFY** | Import `do_*` helpers; thin-wrap `cmd_*`; fix REPL dispatch |
| `ragebot/utils/status_bar.py` | **NEW** | Persistent provider/model status bar |
| `ragebot/utils/error_handler.py` | **MODIFY** | Wire existing class throughout codebase |
| `ragebot/utils/logging_config.py` | **MODIFY** | Wire `BackgroundTaskLogger`/`ProgressState` in engine & embedder |
| `ragebot/utils/ui_helpers.py` | **MODIFY** | Add `show_bottom_error`, `show_bottom_warning` |
| `ragebot/utils/search_formatter.py` | **MODIFY** | Score bar, richer result cards |
| `ragebot/core/engine.py` | **MODIFY** | `ProgressState` in `save()`; typed `RageBotError` in `_generate_answer()` |
| `ragebot/llm/gemini.py` | **MODIFY** | Raise `RageBotError` instead of returning error strings |
| `ragebot/llm/groq.py` | **MODIFY** | Raise `RageBotError` instead of returning error strings |
| `ragebot/llm/ollama.py` | **MODIFY** | Add `BackgroundTaskLogger` |
| `ragebot/storage/snapshot.py` | **MODIFY** | Raise `RageBotError` on missing snapshot |
| `ragebot/auth/provider_auth.py` | **MODIFY** | Live spinner on connection test; richer result panels |
| `ragebot/storage/session_manager.py` | **MODIFY** | Relative timestamps in session list |

---

## 6. Testing Checklist

After applying all changes, verify the following:

### REPL Command Fix
- [ ] `ragebot` launches interactive REPL without error
- [ ] `explain main.py` in REPL works (no `OptionInfo` error)
- [ ] `docs main.py` in REPL works
- [ ] `test main.py` in REPL works
- [ ] `search hello` in REPL works
- [ ] `save`, `init`, `status`, `context`, `snapshot list` all work in REPL
- [ ] `rage explain main.py` (standalone) still works
- [ ] `rage docs main.py` (standalone) still works

### Error Handling
- [ ] Invalid API key shows typed `RageBotError` with recovery steps
- [ ] Rate limit triggers provider-switch prompt
- [ ] Missing snapshot shows actionable error with available list
- [ ] `rage ask "..."` with no index shows helpful "run rage save" message

### Logging
- [ ] No HuggingFace logs on startup
- [ ] `rage save` shows progress state (in logs, not terminal)
- [ ] `rage debug --on` enables debug output
- [ ] `rage debug --off` suppresses it

### UI / UX
- [ ] Status bar appears at top of `ask`, `explain`, `chat`, `docs` output
- [ ] Chat response shows word count in subtitle
- [ ] Search shows score bars
- [ ] Session list shows relative timestamps ("5m ago")
- [ ] Auth connection test shows Live spinner then result panel
- [ ] Rate-limit error shows bottom-right notification

### Tests
```bash
pytest tests/ -v
# All existing 50+ tests should still pass
```

---

## Quick Reference — Import Map

```python
# Core error handling
from ragebot.utils.error_handler import (
    RageBotError, ErrorHandler, ErrorCategory, ErrorSeverity,
    handle_error,          # global convenience function
    get_error_handler,     # global handler instance
)

# Logging
from ragebot.utils.logging_config import (
    suppress_noisy_logs,
    BackgroundTaskLogger,
    ProgressState,
    setup_debug_logging,
    restore_original_logging,
)

# UI helpers
from ragebot.utils.ui_helpers import (
    show_friendly_error, show_success_badge,
    show_warning_badge,  show_info_badge,
    show_bottom_error,   show_bottom_warning,  # new
    show_provider_health_check,
)

# Status bar
from ragebot.utils.status_bar import render_status_bar  # new

# Command helpers (REPL-safe, no Typer)
from ragebot.core.commands import (
    do_init, do_save, do_ask, do_explain,
    do_docs, do_test, do_search, do_status,
    do_context, do_snapshot,
)
```

---

*End of guide. All changes are backward-compatible — existing pytest suite passes without modification.*
