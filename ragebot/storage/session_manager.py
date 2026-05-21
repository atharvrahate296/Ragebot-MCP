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
    
    def preview_session(self, session_id: str, lines: int = 5) -> str:
        """Get a brief preview of a session (last N messages)."""
        history = self.db.get_chat_history(session_id, limit=lines)
        if not history:
            return "[No messages]"
        
        preview_parts = []
        for msg in history[-lines:]:
            role = msg["role"].upper()
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
        table.add_column("Index", style="yellow", width=6)
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
        
        try:
            choice = int(self.console.input("\n[bold cyan]Select session (number):[/bold cyan] ").strip())
            if 1 <= choice <= len(sessions):
                return sessions[choice - 1]["session_id"]
        except (ValueError, IndexError):
            pass
        
        return None
    
    def view_session_full(self, session_id: str) -> None:
        """Display the complete conversation of a session."""
        history = self.db.get_chat_history(session_id, limit=1000)
        if not history:
            self.console.print(f"[yellow]Session {session_id} is empty.[/yellow]")
            return
        
        self.console.print(Panel(f"[bold cyan]Session: {session_id}[/bold cyan]", 
                                border_style="cyan", padding=(0, 2)))
        
        for i, msg in enumerate(history, 1):
            role = msg["role"]
            content = msg["content"]
            
            if role == "user":
                panel_title = f"[bold yellow]User #{i}[/bold yellow]"
                border = "yellow"
            else:
                panel_title = f"[bold green]Assistant #{i}[/bold green]"
                border = "green"
            
            self.console.print(Panel(
                content[:500] + ("..." if len(content) > 500 else ""),
                title=panel_title,
                border_style=border,
                padding=(0, 2),
            ))
        
        self.console.print(f"\n[dim]Total messages: {len(history)}[/dim]")
    
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
