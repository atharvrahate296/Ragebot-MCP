"""
Snapshot Manager - Save and restore project index snapshots.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any


class SnapshotManager:
    def __init__(self, snapshots_dir: Path):
        self.snapshots_dir = snapshots_dir
        snapshots_dir.mkdir(parents=True, exist_ok=True)

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

        return meta

    def list_snapshots(self) -> list[dict]:
        """List all available snapshots."""
        snaps = []
        for snap_dir in sorted(self.snapshots_dir.iterdir()):
            if not snap_dir.is_dir():
                continue
            meta_file = snap_dir / "meta.json"
            if meta_file.exists():
                meta = json.loads(meta_file.read_text())
                # Compute size
                db_file = snap_dir / "ragebot.db"
                size = f"{db_file.stat().st_size / 1024:.1f} KB" if db_file.exists() else "N/A"
                snaps.append({
                    "name": meta.get("name", snap_dir.name),
                    "created": meta.get("created", "Unknown"),
                    "files": meta.get("indexed", 0),
                    "size": size,
                })
        return snaps

    def restore(self, name: str):
        """Restore a snapshot by name."""
        snap_dir = self.snapshots_dir / name
        if not snap_dir.exists():
            raise FileNotFoundError(f"Snapshot '{name}' not found")

        snap_db = snap_dir / "ragebot.db"
        if snap_db.exists():
            dest = self.snapshots_dir.parent / "ragebot.db"
            shutil.copy2(snap_db, dest)

    def delete(self, name: str):
        """Delete a snapshot."""
        snap_dir = self.snapshots_dir / name
        if snap_dir.exists():
            shutil.rmtree(snap_dir)
        else:
            raise FileNotFoundError(f"Snapshot '{name}' not found")
