"""
RageBot Core Engine
────────────────────
Orchestrates directory scanning, parsing, embedding, storage, retrieval, and
LLM answer generation. All import paths use the canonical `ragebot.*` namespace.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

from ragebot.core.config  import ConfigManager
from ragebot.core.scanner import DirectoryScanner
from ragebot.parsers.code_parser import CodeParser
from ragebot.parsers.doc_parser  import DocumentParser
from ragebot.search.embedder     import Embedder
from ragebot.search.retriever    import ContextRetriever
from ragebot.storage.db          import Database
from ragebot.storage.snapshot    import SnapshotManager
from ragebot.agents.context_builder import ContextBuilder
from ragebot.utils.tokens        import TokenCounter
from ragebot.llm.factory         import get_provider


_CODE_EXTS = {".py",".js",".ts",".jsx",".tsx",".java",".cpp",".c",".go",".rs",".rb",".php",".swift",".kt",".cs"}
_DOC_EXTS  = {".pdf",".docx",".txt",".md",".rst"}

_SYSTEM_PROMPT = (
    "You are RageBot, an intelligent code assistant. "
    "Answer the user's question using ONLY the project context provided below. "
    "Be concise, precise, and always cite the source file name when referencing code."
)


class RageBotEngine:
    def __init__(self, project_path: Path, config: ConfigManager) -> None:
        self.project_path = project_path
        self.config       = config
        self.rage_dir     = project_path / ".ragebot"

        self._db:           Optional[Database]         = None
        self._embedder:     Optional[Embedder]         = None
        self._retriever:    Optional[ContextRetriever] = None
        self._snapshot_mgr: Optional[SnapshotManager] = None
        self._token_counter = TokenCounter()

    # ── Lazy properties ───────────────────────────────────────────────────────

    @property
    def db(self) -> Database:
        if self._db is None:
            self._db = Database(self.rage_dir / "ragebot.db")
        return self._db

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = Embedder(
                model_name=self.config.get("embedding_model", "all-MiniLM-L6-v2"),
                cache_dir=self.rage_dir / "embeddings",
            )
        return self._embedder

    @property
    def retriever(self) -> ContextRetriever:
        if self._retriever is None:
            self._retriever = ContextRetriever(
                embedder=self.embedder,
                db=self.db,
                top_k=self.config.get_int("default_top_k", 5),
            )
        return self._retriever

    @property
    def snapshot_mgr(self) -> SnapshotManager:
        if self._snapshot_mgr is None:
            self._snapshot_mgr = SnapshotManager(self.rage_dir / "snapshots")
        return self._snapshot_mgr

    # ── Public API ────────────────────────────────────────────────────────────

    def initialize(self, force: bool = False) -> dict:
        """Create .ragebot workspace and init DB schema."""
        self.rage_dir.mkdir(parents=True, exist_ok=True)
        for sub in ("embeddings", "snapshots", "cache"):
            (self.rage_dir / sub).mkdir(exist_ok=True)

        if force:
            db_path = self.rage_dir / "ragebot.db"
            if db_path.exists():
                db_path.unlink()

        self.db.init_schema()
        scanner = DirectoryScanner(self.project_path, self.config)
        files   = scanner.scan()
        return {"path": str(self.project_path), "file_count": len(files)}

    def save(self, incremental: bool = True, snapshot_name: Optional[str] = None) -> dict:
        """Index (or re-index) the project directory."""
        self.rage_dir.mkdir(parents=True, exist_ok=True)
        self.db.init_schema()

        scanner     = DirectoryScanner(self.project_path, self.config)
        all_files   = scanner.scan()
        code_parser = CodeParser()
        doc_parser  = DocumentParser()

        indexed = skipped = total_tokens = 0

        for file_path in all_files:
            rel = str(file_path.relative_to(self.project_path))
            fhash = self._hash_file(file_path)

            if incremental and self.db.is_indexed(rel, fhash):
                skipped += 1
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                ext     = file_path.suffix.lower()

                if ext in _CODE_EXTS:
                    parsed = code_parser.parse(content, ext, str(file_path))
                elif ext in _DOC_EXTS:
                    parsed = doc_parser.parse(file_path)
                else:
                    parsed = {"summary": content[:500], "chunks": [content], "type": "raw"}

                chunks = parsed.get("chunks", [content[:2000]])
                max_chunks = self.config.get_int("max_chunks_per_file", 20)

                for i, chunk in enumerate(chunks[:max_chunks]):
                    if not chunk.strip():
                        continue
                    embedding = self.embedder.embed(chunk)
                    total_tokens += self._token_counter.count(chunk)
                    self.db.upsert_chunk(
                        file_path=rel, chunk_index=i, content=chunk,
                        embedding=embedding, file_hash=fhash,
                        metadata=json.dumps({
                            "type":      parsed.get("type", "unknown"),
                            "functions": parsed.get("functions", []),
                            "classes":   parsed.get("classes", []),
                            "imports":   parsed.get("imports", []),
                            "summary":   parsed.get("summary", ""),
                        }),
                    )

                self.db.upsert_file(
                    file_path=rel, file_hash=fhash,
                    summary=parsed.get("summary", ""),
                    file_type=parsed.get("type", "unknown"),
                    metadata=json.dumps(parsed.get("meta", {})),
                )
                indexed += 1

            except Exception:
                skipped += 1

        snap_name = snapshot_name or f"snap_{int(time.time())}"
        self.snapshot_mgr.create(snap_name, {
            "project": str(self.project_path),
            "indexed": indexed,
            "timestamp": time.time(),
        })

        return {"indexed": indexed, "skipped": skipped,
                "snapshot_name": snap_name, "token_estimate": total_tokens}

    def ask(self, query: str, mode: str = "smart", top_k: int = 5) -> dict:
        """Semantic search + LLM answer generation."""
        results = self.retriever.retrieve(query=query, top_k=top_k)

        sources: list[dict]          = []
        context_snippets: list[dict] = []

        for r in results:
            sources.append({
                "file":  r["file_path"],
                "score": r["score"],
                "type":  r.get("file_type", "unknown"),
            })
            content = r["content"] if mode != "minimal" else r["content"][:300]
            context_snippets.append({"file": r["file_path"], "content": content})

        answer = self._generate_answer(query, context_snippets)
        provider = get_provider(self.config)

        return {
            "query":            query,
            "answer":           answer,
            "sources":          sources,
            "context_snippets": context_snippets,
            "mode":             mode,
            "provider":         provider.name,
        }

    def chat(self, messages: list[dict], top_k: int = 5) -> str:
        """Multi-turn chat: retrieve context for last user message and answer."""
        last_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
        )
        results  = self.retriever.retrieve(query=last_user, top_k=top_k)
        snippets = [{"file": r["file_path"], "content": r["content"]} for r in results]
        return self._generate_answer(last_user, snippets)

    def search(self, query: str, search_type: str = "semantic", top_k: int = 10) -> list[dict]:
        """Semantic, keyword, or hybrid search."""
        if search_type == "keyword":
            return self.db.keyword_search(query, top_k)
        if search_type == "hybrid":
            sem  = self.retriever.retrieve(query=query, top_k=top_k)
            kw   = self.db.keyword_search(query, top_k)
            seen: set[str] = set()
            merged = []
            for r in sem + kw:
                fp = r.get("file_path") or r.get("file", "")
                if fp not in seen:
                    seen.add(fp)
                    merged.append(r)
            return merged[:top_k]
        # Semantic (default)
        results = self.retriever.retrieve(query=query, top_k=top_k)
        return [{"file": r["file_path"], "score": r["score"], "preview": r["content"][:200],
                 "file_path": r["file_path"], "content": r["content"]} for r in results]

    def explain(self, file_path: str, symbol: Optional[str] = None) -> dict:
        """Explain a file or specific symbol within it."""
        file_data = self.db.get_file(file_path)
        if not file_data:
            return {"error": f"Not indexed: {file_path}. Run `rage save` first."}
        meta = json.loads(file_data.get("metadata", "{}"))

        if symbol:
            chunks = self.db.get_chunks_for_file(file_path)
            relevant = [c["content"] for c in chunks if symbol in c["content"]]
            snippet  = "\n".join(relevant[:3])
            query    = f"Explain the `{symbol}` function/class in {file_path}:\n\n{snippet}"
        else:
            query = f"Explain what {file_path} does based on this summary: {file_data.get('summary', '')}"

        provider = get_provider(self.config)
        answer   = provider.complete(_SYSTEM_PROMPT, query, max_tokens=800)
        return {
            "file":      file_path,
            "symbol":    symbol,
            "summary":   file_data.get("summary", ""),
            "functions": meta.get("functions", []),
            "classes":   meta.get("classes", []),
            "imports":   meta.get("imports", []),
            "explanation": answer,
        }

    def diff_explain(self, diff_text: str) -> str:
        """Explain a git diff in plain English using the LLM."""
        provider = get_provider(self.config)
        prompt   = f"Explain what changed in this git diff in plain English:\n\n{diff_text[:3000]}"
        return provider.complete(_SYSTEM_PROMPT, prompt, max_tokens=600)

    def generate_docs(self, file_path: str) -> str:
        """Auto-generate documentation for a file."""
        file_data = self.db.get_file(file_path)
        if not file_data:
            return f"Error: {file_path} is not indexed."
        chunks = self.db.get_chunks_for_file(file_path)
        code_sample = "\n\n".join(c["content"] for c in chunks[:5])
        provider = get_provider(self.config)
        prompt = (
            f"Generate comprehensive Markdown documentation for the file `{file_path}`.\n\n"
            f"Summary: {file_data.get('summary', '')}\n\n"
            f"Code:\n{code_sample[:3000]}"
        )
        return provider.complete(
            "You are a documentation generator. Output clean Markdown.",
            prompt, max_tokens=1500
        )

    def generate_tests(self, file_path: str) -> str:
        """Generate test cases for a file."""
        file_data = self.db.get_file(file_path)
        if not file_data:
            return f"Error: {file_path} is not indexed."
        meta   = json.loads(file_data.get("metadata", "{}"))
        chunks = self.db.get_chunks_for_file(file_path)
        code   = "\n\n".join(c["content"] for c in chunks[:5])
        provider = get_provider(self.config)
        prompt = (
            f"Generate comprehensive pytest test cases for `{file_path}`.\n"
            f"Functions: {', '.join(meta.get('functions', []))}\n"
            f"Classes: {', '.join(meta.get('classes', []))}\n\n"
            f"Code:\n{code[:3000]}"
        )
        return provider.complete(
            "You are a senior test engineer. Write complete, runnable pytest tests.",
            prompt, max_tokens=2000
        )

    def export_context(self, agent_type: str, focus: Optional[str] = None) -> dict:
        builder = ContextBuilder(
            db=self.db, embedder=self.embedder,
            token_counter=self._token_counter,
        )
        return builder.build(agent_type=agent_type, focus=focus, project_path=self.project_path)

    def get_file_tree(self) -> dict:
        scanner = DirectoryScanner(self.project_path, self.config)
        return {"tree": scanner.get_tree_string()}

    def get_file_context(self, file_path: str) -> dict:
        data = self.db.get_file(file_path)
        if not data:
            return {"error": f"File not indexed: {file_path}"}
        # Functions/classes are stored in chunk metadata (not file metadata)
        chunks = self.db.get_chunks_for_file(file_path)
        chunk_meta: dict = {}
        if chunks:
            try:
                chunk_meta = json.loads(chunks[0].get("metadata", "{}"))
            except Exception:
                chunk_meta = {}
        return {
            "file":      file_path,
            "summary":   data.get("summary", ""),
            "functions": chunk_meta.get("functions", []),
            "classes":   chunk_meta.get("classes", []),
            "imports":   chunk_meta.get("imports", []),
            "type":      data.get("file_type", "unknown"),
        }

    def get_project_summary(self) -> dict:
        files   = self.db.get_all_files()
        entries = [f"{f['file_path']}: {f['summary']}" for f in files if f.get("summary")]
        combined = "\n".join(entries[:30])
        provider = get_provider(self.config)
        if provider.is_available() and combined:
            summary = provider.complete(
                "You are a project analyst. Summarize concisely.",
                f"Summarize this project based on its files:\n\n{combined[:3000]}",
                max_tokens=400,
            )
        else:
            lines = combined.split("\n")
            summary = (
                f"Project contains {len(lines)} indexed file(s). "
                "Key files: " + ", ".join(l.split(":")[0] for l in lines[:5] if l)
            )
        return {"summary": summary}

    def get_project_overview(self) -> dict:
        return self.db.get_stats()

    def get_status(self) -> dict:
        stats   = self.db.get_stats() if (self.rage_dir / "ragebot.db").exists() else {}
        db_path = self.rage_dir / "ragebot.db"
        db_size = f"{db_path.stat().st_size / 1024:.1f} KB" if db_path.exists() else "N/A"

        modified = 0
        if db_path.exists():
            for fp in DirectoryScanner(self.project_path, self.config).scan():
                rel = str(fp.relative_to(self.project_path))
                if not self.db.is_indexed(rel, self._hash_file(fp)):
                    modified += 1

        provider = get_provider(self.config)
        return {
            "project_path":    str(self.project_path),
            "indexed_files":   stats.get("total_files", 0),
            "last_saved":      stats.get("last_updated", "Never"),
            "modified_since":  modified,
            "snapshot_count":  len(self.snapshot_mgr.list_snapshots()),
            "db_size":         db_size,
            "embedding_model": self.config.get("embedding_model", "all-MiniLM-L6-v2"),
            "llm_provider":    provider.name,
            "llm_ready":       provider.is_available(),
        }

    def list_snapshots(self)    -> list:   return self.snapshot_mgr.list_snapshots()
    def restore_snapshot(self, name: str): self.snapshot_mgr.restore(name)
    def delete_snapshot(self, name: str):  self.snapshot_mgr.delete(name)

    def clean(self, all_data: bool = False) -> None:
        import shutil
        cache = self.rage_dir / "cache"
        if cache.exists():
            shutil.rmtree(cache); cache.mkdir()
        if all_data and self.rage_dir.exists():
            shutil.rmtree(self.rage_dir)

    # ── Private ───────────────────────────────────────────────────────────────

    def _hash_file(self, path: Path) -> str:
        try:
            return hashlib.md5(path.read_bytes()).hexdigest()
        except Exception:
            return ""

    def _generate_answer(self, query: str, snippets: list[dict]) -> str:
        provider = get_provider(self.config)
        if not snippets:
            return "No relevant context found. Run `rage save` to index your project first."
        context_text = "\n\n".join(
            f"[{s['file']}]\n{s['content'][:600]}" for s in snippets[:5]
        )
        if not provider.is_available():
            return (
                f"Found {len(snippets)} relevant context(s). "
                f"Top result from: `{snippets[0]['file']}`\n\n"
                "Configure an LLM to get AI-generated answers: `rage auth login gemini`"
            )
        user_prompt = f"Project context:\n\n{context_text}\n\nQuestion: {query}"
        return provider.complete(_SYSTEM_PROMPT, user_prompt,
                                 max_tokens=self.config.get_int("max_answer_tokens", 1000))
