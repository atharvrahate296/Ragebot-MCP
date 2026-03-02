"""
File Watcher - Monitors project directory for changes and triggers re-indexing.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from ragebot.core.engine import RageBotEngine

console = Console()


class FileWatcher:
    def __init__(self, engine: "RageBotEngine", debounce: int = 3):
        self.engine = engine
        self.debounce = debounce
        self._pending = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    def start(self):
        """Start watching using watchdog if available, else polling."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class Handler(FileSystemEventHandler):
                def __init__(self, watcher):
                    self._watcher = watcher

                def on_any_event(self, event):
                    if not event.is_directory:
                        # Skip .ragebot dir changes
                        if ".ragebot" not in str(event.src_path):
                            self._watcher._schedule_reindex()

            observer = Observer()
            observer.schedule(Handler(self), str(self.engine.project_path), recursive=True)
            observer.start()
            console.print("[green]👁️  Watching with watchdog...[/green]")
            try:
                while not self._stop_event.is_set():
                    time.sleep(1)
            except KeyboardInterrupt:
                console.print("\n[yellow]Watch stopped.[/yellow]")
            finally:
                observer.stop()
                observer.join()

        except ImportError:
            console.print("[yellow]watchdog not installed, using polling mode.[/yellow]")
            self._poll()

    def _poll(self):
        """Fallback polling watcher."""
        last_snapshot = self._get_snapshot()
        console.print("[cyan]Polling every 5 seconds...[/cyan]")
        try:
            while True:
                time.sleep(5)
                current = self._get_snapshot()
                if current != last_snapshot:
                    last_snapshot = current
                    self._reindex()
        except KeyboardInterrupt:
            console.print("\n[yellow]Watch stopped.[/yellow]")

    def _get_snapshot(self) -> dict:
        snapshot = {}
        try:
            for f in self.engine.project_path.rglob("*"):
                if f.is_file() and ".ragebot" not in str(f):
                    try:
                        snapshot[str(f)] = f.stat().st_mtime
                    except OSError:
                        pass
        except Exception:
            pass
        return snapshot

    def _schedule_reindex(self):
        with self._lock:
            if self._pending:
                return
            self._pending = True

        def delayed():
            time.sleep(self.debounce)
            with self._lock:
                self._pending = False
            self._reindex()

        threading.Thread(target=delayed, daemon=True).start()

    def _reindex(self):
        console.print("[cyan]🔄 Changes detected, re-indexing...[/cyan]")
        try:
            result = self.engine.save(incremental=True)
            console.print(
                f"[green]✓ Re-indexed {result['indexed']} files "
                f"(skipped {result['skipped']})[/green]"
            )
        except Exception as e:
            console.print(f"[red]Error during re-index: {e}[/red]")
