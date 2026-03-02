"""
Database — SQLite storage layer for files, chunks, and embeddings.
All import paths use the canonical ragebot.* namespace.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def init_schema(self) -> None:
        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS files (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path   TEXT    UNIQUE NOT NULL,
                    file_hash   TEXT    NOT NULL,
                    file_type   TEXT    DEFAULT 'unknown',
                    summary     TEXT    DEFAULT '',
                    metadata    TEXT    DEFAULT '{}',
                    indexed_at  REAL    DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path   TEXT    NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content     TEXT    NOT NULL,
                    embedding   TEXT    DEFAULT '[]',
                    file_hash   TEXT    DEFAULT '',
                    metadata    TEXT    DEFAULT '{}',
                    created_at  REAL    DEFAULT 0,
                    UNIQUE(file_path, chunk_index)
                );
                CREATE TABLE IF NOT EXISTS chat_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT    NOT NULL,
                    role        TEXT    NOT NULL,
                    content     TEXT    NOT NULL,
                    created_at  REAL    DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_path);
                CREATE INDEX IF NOT EXISTS idx_files_hash  ON files(file_hash);
                CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id);
            """)

    # ── Files ─────────────────────────────────────────────────────────────────

    def upsert_file(self, file_path: str, file_hash: str,
                    summary: str = "", file_type: str = "unknown",
                    metadata: str = "{}") -> None:
        with self.conn:
            self.conn.execute("""
                INSERT INTO files (file_path, file_hash, file_type, summary, metadata, indexed_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(file_path) DO UPDATE SET
                    file_hash=excluded.file_hash, file_type=excluded.file_type,
                    summary=excluded.summary, metadata=excluded.metadata,
                    indexed_at=excluded.indexed_at
            """, (file_path, file_hash, file_type, summary, metadata, time.time()))

    def get_file(self, file_path: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM files WHERE file_path=?", (file_path,)
        ).fetchone()
        return dict(row) if row else None

    def get_all_files(self) -> list[dict]:
        return [dict(r) for r in
                self.conn.execute("SELECT * FROM files ORDER BY indexed_at DESC").fetchall()]

    def is_indexed(self, file_path: str, file_hash: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM files WHERE file_path=? AND file_hash=?", (file_path, file_hash)
        ).fetchone() is not None

    def delete_file(self, file_path: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM files  WHERE file_path=?", (file_path,))
            self.conn.execute("DELETE FROM chunks WHERE file_path=?", (file_path,))

    # ── Chunks ────────────────────────────────────────────────────────────────

    def upsert_chunk(self, file_path: str, chunk_index: int, content: str,
                     embedding: list, file_hash: str = "", metadata: str = "{}") -> None:
        with self.conn:
            self.conn.execute("""
                INSERT INTO chunks (file_path, chunk_index, content, embedding, file_hash, metadata, created_at)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(file_path, chunk_index) DO UPDATE SET
                    content=excluded.content, embedding=excluded.embedding,
                    file_hash=excluded.file_hash, metadata=excluded.metadata,
                    created_at=excluded.created_at
            """, (file_path, chunk_index, content, json.dumps(embedding), file_hash, metadata, time.time()))

    def get_all_chunks(self) -> list[dict]:
        return [dict(r) for r in
                self.conn.execute(
                    "SELECT file_path, chunk_index, content, embedding, metadata FROM chunks"
                ).fetchall()]

    def get_chunks_for_file(self, file_path: str) -> list[dict]:
        return [dict(r) for r in
                self.conn.execute(
                    "SELECT * FROM chunks WHERE file_path=? ORDER BY chunk_index",
                    (file_path,)
                ).fetchall()]

    def keyword_search(self, query: str, top_k: int = 10) -> list[dict]:
        pattern = f"%{query}%"
        rows = self.conn.execute("""
            SELECT DISTINCT c.file_path, c.content, f.file_type, f.summary,
                   (LENGTH(c.content) - LENGTH(REPLACE(LOWER(c.content), LOWER(?), '')))
                   / MAX(LENGTH(?),1) AS score
            FROM chunks c
            LEFT JOIN files f ON c.file_path = f.file_path
            WHERE c.content LIKE ?
            ORDER BY score DESC
            LIMIT ?
        """, (query, query, pattern, top_k)).fetchall()
        return [
            {
                "file": dict(r)["file_path"], "file_path": dict(r)["file_path"],
                "score": float(dict(r).get("score", 0)),
                "preview": dict(r)["content"][:200], "content": dict(r)["content"],
                "file_type": dict(r).get("file_type", "unknown"),
            }
            for r in rows
        ]

    # ── Chat history ──────────────────────────────────────────────────────────

    def save_chat_message(self, session_id: str, role: str, content: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO chat_history (session_id, role, content, created_at) VALUES (?,?,?,?)",
                (session_id, role, content, time.time()),
            )

    def get_chat_history(self, session_id: str, limit: int = 20) -> list[dict]:
        rows = self.conn.execute("""
            SELECT role, content, created_at FROM chat_history
            WHERE session_id=? ORDER BY created_at DESC LIMIT ?
        """, (session_id, limit)).fetchall()
        return list(reversed([dict(r) for r in rows]))

    def list_chat_sessions(self) -> list[dict]:
        rows = self.conn.execute("""
            SELECT session_id,
                   MIN(created_at) as started,
                   MAX(created_at) as last_msg,
                   COUNT(*) as messages
            FROM chat_history GROUP BY session_id ORDER BY last_msg DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def delete_chat_session(self, session_id: str) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM chat_history WHERE session_id=?", (session_id,))

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        fc  = self.conn.execute("SELECT COUNT(*) as c FROM files").fetchone()["c"]
        cc  = self.conn.execute("SELECT COUNT(*) as c FROM chunks").fetchone()["c"]
        ts  = self.conn.execute("SELECT MAX(indexed_at) as t FROM files").fetchone()["t"]
        tcs = self.conn.execute(
            "SELECT file_type, COUNT(*) as c FROM files GROUP BY file_type"
        ).fetchall()
        result: dict = {
            "total_files":  fc,
            "total_chunks": cc,
            "last_updated": (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
                if ts else "Never"
            ),
        }
        for row in tcs:
            result[f"{row['file_type']}_files"] = row["c"]
        return result

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
