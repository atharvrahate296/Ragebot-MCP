# ragebot/storage/session_manager.py
"""
Session Manager - Interactive session management with preview and selection.
Handles listing, previewing, viewing, and deleting chat sessions.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ragebot.storage.db import Database

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown


class SessionManager:
    """Manage chat session lifecycle and interactions."""
    
    def __init__(self, db: "Database", console: Optional[Console] = None):
        self.db = db
        self.console = console or Console()
    
    def list_sessions(self, limit: int = 20) -> list[dict]:
        """Get all chat sessions with metadata."""
        sessions = self.db.list_chat_sessions()
        return sessions[:limit]
    
    def get_session_by_number(self, number: int) -> Optional[str]:
        """Get session_id by its display number (1-indexed)."""
        sessions = self.list_sessions()
        if 1 <= number <= len(sessions):
            return sessions[number - 1]["session_id"]
        return None
    
    def preview_session(self, session_id: str, lines: int = 5) -> str:
        """Get a brief preview of a session (last N messages)."""
        history = self.db.get_chat_history(session_id, limit=lines)
        if not history:
            return "[No messages]"
        
        preview_parts = []
        for msg in history[-lines:]:
            role = "Ragebot" if msg["role"] == "assistant" else msg["role"].upper()
            content = msg["content"][:80]
            preview_parts.append(f"{role}: {content}...")
        return "\n".join(preview_parts)
    
    def display_sessions_interactive(self) -> Optional[str]:
        """
        Display sessions in an interactive table.
        Returns selected session_id or None.
        """
        sessions = self.list_sessions()
        if not sessions:
            self.console.print("[yellow]No chat sessions found.[/yellow]")
            return None
        
        table = Table(title="📋 Chat Sessions", box=None, header_style="bold cyan")
        table.add_column("#", style="yellow", width=6)
        table.add_column("Session ID", style="cyan", width=24)
        table.add_column("Started", style="dim", width=16)
        table.add_column("Messages", style="green", width=10)
        table.add_column("Preview", style="white", width=40)
        
        for i, sess in enumerate(sessions, 1):
            sid = sess["session_id"][:20]
            started = datetime.fromtimestamp(sess["started"]).strftime("%Y-%m-%d %H:%M")
            msg_count = str(sess["messages"])
            preview = self.preview_session(sess["session_id"], lines=1).replace("\n", " ")[:35]
            
            table.add_row(str(i), sid, started, msg_count, preview)
        
        self.console.print(table)
        self.console.print("\n[dim]Enter a session number to view, or press Enter to cancel.[/dim]")
        
        try:
            choice = self.console.input("\n[bold cyan]Select session (#):[/bold cyan] ").strip()
            if not choice:
                return None
            num = int(choice)
            if 1 <= num <= len(sessions):
                return sessions[num - 1]["session_id"]
        except (ValueError, IndexError):
            pass
        
        return None
    
    def view_session_full(self, session_id: str) -> None:
        """Display the complete conversation of a session with Ragebot labels."""
        history = self.db.get_chat_history(session_id, limit=1000)
        if not history:
            self.console.print(f"[yellow]Session {session_id} not found or is empty.[/yellow]")
            return

        # Compute timestamp info for header
        started_ts = history[0].get("timestamp") if history else None
        started_str = ""
        if started_ts:
            try:
                started_str = f"  •  Started {datetime.fromtimestamp(float(started_ts)).strftime('%Y-%m-%d %H:%M')}"
            except Exception:
                pass

        self.console.print(Panel(
            f"[bold cyan]Session: {session_id}[/bold cyan]{started_str}\n"
            f"[dim]{len(history)} message(s) in this conversation[/dim]",
            border_style="cyan", padding=(0, 2),
            title="[bold]💬 Chat History[/bold]",
            title_align="left",
        ))

        msg_num = 0
        for msg in history:
            role = msg["role"]
            content = msg["content"]
            msg_num += 1

            if role == "user":
                panel_title = f"[bold yellow]You[/bold yellow]  [dim]#{msg_num}[/dim]"
                border = "yellow"
                body = content
            else:
                panel_title = f"[bold green]Ragebot[/bold green]  [dim]#{msg_num}[/dim]"
                border = "green"
                body = Markdown(content)

            self.console.print(Panel(
                body,
                title=panel_title,
                border_style=border,
                padding=(0, 2),
            ))

        self.console.print(
            f"\n[dim]─── End of history ({len(history)} messages) ───[/dim]\n"
        )
    
    def show_session_by_number(self, number: int) -> bool:
        """Show a session by its display number. Returns True if found."""
        session_id = self.get_session_by_number(number)
        if session_id:
            self.view_session_full(session_id)
            return True
        self.console.print(f"[red]Session #{number} not found.[/red]")
        return False
    
    def delete_session_by_number(self, number: int) -> bool:
        """Delete a session by its display number. Returns True if deleted."""
        session_id = self.get_session_by_number(number)
        if not session_id:
            self.console.print(f"[red]Session #{number} not found.[/red]")
            return False
        
        from rich.prompt import Confirm
        if Confirm.ask(f"\n[bold red]Delete session #{number} ({session_id[:20]})?[/bold red]", default=False):
            self.db.delete_chat_session(session_id)
            self.console.print(f"[green]✓ Session #{number} deleted.[/green]")
            return True
        return False

    def delete_session_interactive(self) -> Optional[str]:
        """Interactively select and delete a session."""
        session_id = self.display_sessions_interactive()
        if not session_id:
            return None
        
        from rich.prompt import Confirm
        if Confirm.ask(f"\n[bold red]Delete session {session_id[:20]}?[/bold red]", default=False):
            self.db.delete_chat_session(session_id)
            return session_id
        
        return None
    
    def get_session_history(self, session_id: str) -> list[dict]:
        """Get full message history for a session (for context continuation)."""
        history = self.db.get_chat_history(session_id, limit=1000)
        return [{"role": m["role"], "content": m["content"]} for m in history]

    def export_session(self, session_id: str, output_path: Path) -> bool:
        """Export a session to JSON file."""
        history = self.db.get_chat_history(session_id, limit=10000)
        if not history:
            return False
        
        export_data = {
            "session_id": session_id,
            "message_count": len(history),
            "messages": history,
        }
        
        try:
            output_path.write_text(json.dumps(export_data, indent=2))
            return True
        except Exception:
            return False
    
    def clear_old_sessions(self, days: int = 30) -> int:
        """Delete sessions older than N days. Returns count deleted."""
        import time
        cutoff = time.time() - (days * 86400)
        sessions = self.db.list_chat_sessions()
        deleted = 0
        
        for sess in sessions:
            if sess["last_msg"] < cutoff:
                self.db.delete_chat_session(sess["session_id"])
                deleted += 1
        
        return deleted
    
    def create_session_snapshot(self, session_id: str) -> dict:
        """Create a point-in-time snapshot of a session."""
        history = self.db.get_chat_history(session_id, limit=10000)
        return {
            "session_id": session_id,
            "messages": history,
            "snapshot_time": datetime.now().isoformat(),
            "message_count": len(history),
        }
