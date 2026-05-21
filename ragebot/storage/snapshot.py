"""
Snapshot Manager - Save and restore project index snapshots.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Optional

from ragebot.utils.error_handler import RageBotError, ErrorCategory, ErrorSeverity


class SnapshotManager:
    def __init__(self, snapshots_dir: Path):
        self.snapshots_dir = snapshots_dir
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        self._active_snapshot: Optional[str] = None

    def create(self, name: str, metadata: dict) -> dict:
        """Create a new snapshot with the given name."""
        snap_dir = self.snapshots_dir / name
        snap_dir.mkdir(exist_ok=True)

        meta = {
            "name": name,
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": time.time(),
            **metadata,
        }
        (snap_dir / "meta.json").write_text(json.dumps(meta, indent=2))

        # Copy current DB into snapshot
        db_path = self.snapshots_dir.parent / "ragebot.db"
        if db_path.exists():
            shutil.copy2(db_path, snap_dir / "ragebot.db")

        # Mark this as active
        self._set_active(name)
        return meta

    def list_snapshots(self) -> list[dict]:
        """List all available snapshots."""
        snaps = []
        active = self._get_active()
        for snap_dir in sorted(self.snapshots_dir.iterdir()):
            if not snap_dir.is_dir():
                continue
            meta_file = snap_dir / "meta.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text())
                except (json.JSONDecodeError, OSError):
                    continue
                # Compute size
                db_file = snap_dir / "ragebot.db"
                size = f"{db_file.stat().st_size / 1024:.1f} KB" if db_file.exists() else "N/A"
                snaps.append({
                    "name": meta.get("name", snap_dir.name),
                    "created": meta.get("created", "Unknown"),
                    "files": meta.get("indexed", 0),
                    "size": size,
                    "active": meta.get("name", snap_dir.name) == active,
                })
        return snaps

    def restore(self, name: str):
        """Restore a snapshot by name."""
        snap_dir = self.snapshots_dir / name
        if not snap_dir.exists():
            # Try fuzzy match
            available = [d.name for d in self.snapshots_dir.iterdir() if d.is_dir()]
            matches = [s for s in available if name in s]
            if matches:
                snap_dir = self.snapshots_dir / matches[0]
                name = matches[0]
            else:
                available_str = ", ".join(available) if available else "none"
                raise FileNotFoundError(
                    f"Snapshot '{name}' not found.\n"
                    f"Available snapshots: {available_str}\n"
                    f"List all: rage snapshot list"
                )

        snap_db = snap_dir / "ragebot.db"
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

        dest = self.snapshots_dir.parent / "ragebot.db"
        # Backup current DB before restore
        if dest.exists():
            backup = dest.with_suffix(".db.bak")
            shutil.copy2(dest, backup)
        
        shutil.copy2(snap_db, dest)
        self._set_active(name)

    def delete(self, name: str):
        """Delete a snapshot."""
        snap_dir = self.snapshots_dir / name
        if snap_dir.exists():
            shutil.rmtree(snap_dir)
            # Clear active if this was the active snapshot
            if self._get_active() == name:
                self._clear_active()
        else:
            available = [d.name for d in self.snapshots_dir.iterdir() if d.is_dir()]
            available_str = ", ".join(available) if available else "none"
            raise FileNotFoundError(
                f"Snapshot '{name}' not found.\n"
                f"Available snapshots: {available_str}"
            )

    def _get_active(self) -> Optional[str]:
        """Get the currently active snapshot name."""
        active_file = self.snapshots_dir / ".active"
        if active_file.exists():
            try:
                return active_file.read_text().strip()
            except OSError:
                return None
        return self._active_snapshot

    def _set_active(self, name: str) -> None:
        """Set the active snapshot."""
        self._active_snapshot = name
        active_file = self.snapshots_dir / ".active"
        try:
            active_file.write_text(name)
        except OSError:
            pass

    def _clear_active(self) -> None:
        """Clear the active snapshot marker."""
        self._active_snapshot = None
        active_file = self.snapshots_dir / ".active"
        if active_file.exists():
            try:
                active_file.unlink()
            except OSError:
                pass
