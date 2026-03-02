"""
RageBot MCP — Full Test Suite
Run:  pytest tests/ -v
"""
import json
import tempfile
import time
from pathlib import Path

import pytest


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def tmp_project(tmp_path):
    """A temporary project with sample source files."""
    (tmp_path / "main.py").write_text(
        '"""Main module."""\n\ndef hello(name: str) -> str:\n    """Return greeting."""\n    return f"Hello, {name}!"\n\nclass Greeter:\n    """Greeter class."""\n    def greet(self, name):\n        return hello(name)\n'
    )
    (tmp_path / "app.js").write_text(
        "const express = require('express');\nfunction handleRequest(req, res) { res.json({ok:true}); }\n"
    )
    (tmp_path / "README.md").write_text("# Test Project\n\nA sample project for RageBot testing.\n")
    (tmp_path / "config.json").write_text('{"env":"test","port":3000}')
    return tmp_path


@pytest.fixture
def cfg():
    from ragebot.core.config import ConfigManager
    c = ConfigManager()
    c.set("llm_provider", "none")
    return c


@pytest.fixture
def db(tmp_path):
    from ragebot.storage.db import Database
    d = Database(tmp_path / ".ragebot" / "test.db")
    d.init_schema()
    return d


@pytest.fixture
def engine(tmp_project, cfg):
    from ragebot.core.engine import RageBotEngine
    return RageBotEngine(project_path=tmp_project, config=cfg)


# ══════════════════════════════════════════════════════════════════════════════
# Config
# ══════════════════════════════════════════════════════════════════════════════

class TestConfig:
    def test_defaults_present(self, cfg):
        assert cfg.get("embedding_model") is not None
        assert cfg.get("llm_provider") in ("gemini", "grok", "none")

    def test_set_and_get(self, cfg):
        cfg.set("chunk_size", "256")
        assert cfg.get("chunk_size") == "256"

    def test_get_int(self, cfg):
        cfg.set("default_top_k", "7")
        assert cfg.get_int("default_top_k") == 7

    def test_get_bool(self, cfg):
        cfg.set("auto_watch", "true")
        assert cfg.get_bool("auto_watch") is True
        cfg.set("auto_watch", "false")
        assert cfg.get_bool("auto_watch") is False

    def test_ignore_patterns(self, cfg):
        patterns = cfg.get_ignore_patterns()
        assert ".git" in patterns
        assert "node_modules" in patterns

    def test_secrets_not_in_data(self, cfg):
        from ragebot.core.config import _SECRET_KEYS
        for k in _SECRET_KEYS:
            assert k not in cfg._data, f"{k} leaked into _data"

    def test_secret_keys_set(self, cfg):
        from ragebot.core.config import _SECRET_KEYS
        assert "gemini_api_key" in _SECRET_KEYS
        assert "grok_api_key"   in _SECRET_KEYS

    def test_get_all_masks_secrets(self, cfg):
        all_cfg = cfg.get_all()
        # If no key is set, value should be '' (not the real key)
        for k in cfg.secret_keys:
            val = all_cfg.get(k, "")
            # Should be empty or masked (not a long plain-text key)
            assert len(val) == 0 or val.startswith("*") or len(val) <= 12

    def test_reset(self, cfg):
        cfg.set("chunk_size", "999")
        cfg.reset()
        assert cfg.get("chunk_size") != "999"


# ══════════════════════════════════════════════════════════════════════════════
# LLM Providers
# ══════════════════════════════════════════════════════════════════════════════

class TestLLMProviders:
    def test_gemini_not_available_without_key(self):
        from ragebot.llm.gemini import GeminiProvider
        p = GeminiProvider(api_key="", model="gemini-1.5-flash")
        assert p.is_available() is False
        assert "gemini" in p.name.lower()

    def test_grok_not_available_without_key(self):
        from ragebot.llm.grok import GrokProvider
        p = GrokProvider(api_key="", model="grok-3-mini")
        assert p.is_available() is False
        assert "grok" in p.name.lower()

    def test_noop_provider(self):
        from ragebot.llm.noop import NoopProvider
        p = NoopProvider()
        assert p.is_available() is False
        assert p.name == "none"
        assert "No LLM" in p.complete("sys", "user")

    def test_factory_returns_noop_for_none(self, cfg):
        cfg.set("llm_provider", "none")
        from ragebot.llm.factory import get_provider
        p = get_provider(cfg)
        assert p.name == "none"

    def test_factory_returns_gemini(self, cfg):
        cfg.set("llm_provider", "gemini")
        from ragebot.llm.factory import get_provider
        from ragebot.llm.gemini  import GeminiProvider
        p = get_provider(cfg)
        assert isinstance(p, GeminiProvider)

    def test_factory_returns_grok(self, cfg):
        cfg.set("llm_provider", "grok")
        from ragebot.llm.factory import get_provider
        from ragebot.llm.grok import GrokProvider
        p = get_provider(cfg)
        assert isinstance(p, GrokProvider)


# ══════════════════════════════════════════════════════════════════════════════
# Scanner
# ══════════════════════════════════════════════════════════════════════════════

class TestScanner:
    def test_finds_project_files(self, tmp_project, cfg):
        from ragebot.core.scanner import DirectoryScanner
        s = DirectoryScanner(tmp_project, cfg)
        files = s.scan()
        names = [f.name for f in files]
        assert "main.py" in names
        assert "README.md" in names

    def test_ignores_git_dir(self, tmp_project, cfg):
        from ragebot.core.scanner import DirectoryScanner
        git = tmp_project / ".git"
        git.mkdir()
        (git / "HEAD").write_text("ref: refs/heads/main")
        s = DirectoryScanner(tmp_project, cfg)
        files = s.scan()
        assert not any(".git" in str(f) for f in files)

    def test_classify_code(self, tmp_project, cfg):
        from ragebot.core.scanner import DirectoryScanner
        s = DirectoryScanner(tmp_project, cfg)
        assert s.classify(tmp_project / "main.py") == "code"

    def test_classify_doc(self, tmp_project, cfg):
        from ragebot.core.scanner import DirectoryScanner
        s = DirectoryScanner(tmp_project, cfg)
        assert s.classify(tmp_project / "README.md") == "doc"

    def test_tree_contains_files(self, tmp_project, cfg):
        from ragebot.core.scanner import DirectoryScanner
        s = DirectoryScanner(tmp_project, cfg)
        tree = s.get_tree_string()
        assert "main.py" in tree
        assert "README.md" in tree


# ══════════════════════════════════════════════════════════════════════════════
# Code Parser
# ══════════════════════════════════════════════════════════════════════════════

class TestCodeParser:
    def test_parse_python(self):
        from ragebot.parsers.code_parser import CodeParser
        p = CodeParser()
        result = p.parse("def foo():\n    pass\n\nclass Bar:\n    pass\n\nimport os\n", ".py", "t.py")
        assert "foo" in result["functions"]
        assert "Bar" in result["classes"]
        assert "os"  in result["imports"]
        assert result["type"] == "code"

    def test_parse_javascript(self):
        from ragebot.parsers.code_parser import CodeParser
        result = CodeParser().parse("const r = require('fs');\nfunction go() {}", ".js", "a.js")
        assert result["type"] == "code"

    def test_parse_go(self):
        from ragebot.parsers.code_parser import CodeParser
        code = 'package main\nimport "fmt"\nfunc main() { fmt.Println("hi") }\ntype S struct{}'
        result = CodeParser().parse(code, ".go", "m.go")
        assert "main" in result["functions"]
        assert "S" in result["classes"]

    def test_chunks_created(self):
        from ragebot.parsers.code_parser import CodeParser
        code = "\n".join(f"def func_{i}(): pass" for i in range(50))
        result = CodeParser().parse(code, ".py", "big.py")
        assert len(result["chunks"]) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# Document Parser
# ══════════════════════════════════════════════════════════════════════════════

class TestDocParser:
    def test_parse_markdown(self, tmp_path):
        from ragebot.parsers.doc_parser import DocumentParser
        f = tmp_path / "doc.md"
        f.write_text("# Title\n\nParagraph one.\n\n## Section\n\nMore text here.")
        result = DocumentParser().parse(f)
        assert result["type"] == "markdown"
        assert len(result["chunks"]) >= 1
        assert result["summary"]

    def test_parse_text(self, tmp_path):
        from ragebot.parsers.doc_parser import DocumentParser
        f = tmp_path / "notes.txt"
        f.write_text("Line 1.\nLine 2.\nLine 3.\n")
        result = DocumentParser().parse(f)
        assert result["type"] == "text"


# ══════════════════════════════════════════════════════════════════════════════
# Database
# ══════════════════════════════════════════════════════════════════════════════

class TestDatabase:
    def test_upsert_and_retrieve_file(self, db):
        db.upsert_file("src/main.py", "abc", "Main", "code", "{}")
        row = db.get_file("src/main.py")
        assert row is not None
        assert row["file_hash"] == "abc"

    def test_is_indexed(self, db):
        db.upsert_file("a.py", "h1", "", "code", "{}")
        assert db.is_indexed("a.py", "h1")
        assert not db.is_indexed("a.py", "wrong")
        assert not db.is_indexed("missing.py", "h1")

    def test_upsert_chunk(self, db):
        db.upsert_chunk("a.py", 0, "def foo(): pass", [0.1, 0.2], "h1")
        chunks = db.get_all_chunks()
        assert len(chunks) == 1
        assert chunks[0]["content"] == "def foo(): pass"

    def test_get_chunks_for_file(self, db):
        db.upsert_chunk("x.py", 0, "chunk 0", [], "h")
        db.upsert_chunk("x.py", 1, "chunk 1", [], "h")
        db.upsert_chunk("y.py", 0, "chunk y", [], "h")
        chunks = db.get_chunks_for_file("x.py")
        assert len(chunks) == 2
        assert all(c["file_path"] == "x.py" for c in chunks)

    def test_keyword_search(self, db):
        db.upsert_file("auth.py", "h", "", "code", "{}")
        db.upsert_chunk("auth.py", 0, "def login(user, pw): pass", [], "h")
        results = db.keyword_search("login", top_k=5)
        assert any("login" in r["content"] for r in results)

    def test_chat_history(self, db):
        db.save_chat_message("s1", "user", "hello")
        db.save_chat_message("s1", "assistant", "hi!")
        hist = db.get_chat_history("s1")
        assert len(hist) == 2
        assert hist[0]["role"] == "user"
        sessions = db.list_chat_sessions()
        assert any(s["session_id"] == "s1" for s in sessions)
        db.delete_chat_session("s1")
        assert len(db.get_chat_history("s1")) == 0

    def test_stats(self, db):
        db.upsert_file("a.py", "h1", "", "code", "{}")
        db.upsert_file("b.md", "h2", "", "doc",  "{}")
        stats = db.get_stats()
        assert stats["total_files"] == 2


# ══════════════════════════════════════════════════════════════════════════════
# Token Counter
# ══════════════════════════════════════════════════════════════════════════════

class TestTokenCounter:
    def test_count_positive(self):
        from ragebot.utils.tokens import TokenCounter
        assert TokenCounter().count("Hello world") > 0

    def test_count_empty(self):
        from ragebot.utils.tokens import TokenCounter
        assert TokenCounter().count("") == 0

    def test_truncate(self):
        from ragebot.utils.tokens import TokenCounter
        tc   = TokenCounter()
        text = "word " * 2000
        t    = tc.truncate(text, 50)
        assert tc.count(t) <= 60


# ══════════════════════════════════════════════════════════════════════════════
# Embedder
# ══════════════════════════════════════════════════════════════════════════════

class TestEmbedder:
    def test_fallback_embedding_shape(self):
        from ragebot.search.embedder import Embedder
        e = Embedder.__new__(Embedder)
        e._model = None; e._tried_import = True; e._cache = {}; e.cache_dir = None
        v = e._fallback_embedding("hello world")
        assert len(v) == 128
        import math
        mag = math.sqrt(sum(x * x for x in v))
        assert abs(mag - 1.0) < 0.01

    def test_embed_returns_list(self, tmp_path):
        from ragebot.search.embedder import Embedder
        e = Embedder(cache_dir=tmp_path / "emb")
        v = e.embed("test sentence")
        assert isinstance(v, list) and len(v) > 0

    def test_caching(self, tmp_path):
        from ragebot.search.embedder import Embedder
        e = Embedder(cache_dir=tmp_path / "emb")
        assert e.embed("abc") == e.embed("abc")


# ══════════════════════════════════════════════════════════════════════════════
# Snapshot Manager
# ══════════════════════════════════════════════════════════════════════════════

class TestSnapshotManager:
    def test_create_list_delete(self, tmp_path):
        from ragebot.storage.snapshot import SnapshotManager
        mgr = SnapshotManager(tmp_path / "snaps")
        mgr.create("snap1", {"indexed": 5})
        snaps = mgr.list_snapshots()
        assert len(snaps) == 1 and snaps[0]["name"] == "snap1"
        mgr.delete("snap1")
        assert len(mgr.list_snapshots()) == 0

    def test_delete_missing_raises(self, tmp_path):
        from ragebot.storage.snapshot import SnapshotManager
        mgr = SnapshotManager(tmp_path / "snaps")
        with pytest.raises(FileNotFoundError):
            mgr.delete("nonexistent")


# ══════════════════════════════════════════════════════════════════════════════
# Engine — integration
# ══════════════════════════════════════════════════════════════════════════════

class TestEngineIntegration:
    def test_init(self, engine):
        result = engine.initialize(force=True)
        assert result["file_count"] >= 2

    def test_save_and_status(self, engine):
        engine.initialize(force=True)
        result = engine.save(incremental=False)
        assert result["indexed"] >= 2
        status = engine.get_status()
        assert status["indexed_files"] >= 2
        assert status["llm_provider"] == "none"
        assert status["llm_ready"] is False

    def test_file_context(self, engine):
        engine.initialize(force=True)
        engine.save(incremental=False)
        ctx = engine.get_file_context("main.py")
        assert "hello" in ctx.get("functions", [])
        assert "Greeter" in ctx.get("classes", [])

    def test_search_keyword(self, engine):
        engine.initialize(force=True)
        engine.save(incremental=False)
        results = engine.search("hello", search_type="keyword", top_k=5)
        assert len(results) >= 1

    def test_file_tree(self, engine):
        engine.initialize()
        tree = engine.get_file_tree()
        assert "main.py" in tree["tree"]

    def test_project_overview(self, engine):
        engine.initialize(force=True)
        engine.save(incremental=False)
        overview = engine.get_project_overview()
        assert "total_files" in overview

    def test_incremental_skip(self, engine):
        engine.initialize(force=True)
        r1 = engine.save(incremental=False)
        r2 = engine.save(incremental=True)
        assert r2["skipped"] >= r1["indexed"]

    def test_snapshots(self, engine):
        engine.initialize(force=True)
        engine.save(incremental=False, snapshot_name="test-snap")
        snaps = engine.list_snapshots()
        assert any(s["name"] == "test-snap" for s in snaps)
        engine.delete_snapshot("test-snap")

    def test_clean(self, engine):
        engine.initialize(force=True)
        engine.clean(all_data=False)
        assert (engine.rage_dir / "cache").exists()


# ══════════════════════════════════════════════════════════════════════════════
# MCP Server
# ══════════════════════════════════════════════════════════════════════════════

class TestMCPServer:
    @pytest.fixture
    def server(self, engine):
        from ragebot.mcp.server import RageBotMCPServer
        engine.initialize(force=True)
        engine.save(incremental=False)
        return RageBotMCPServer(project_path=engine.project_path, config=engine.config)

    def test_initialize_handshake(self, server):
        resp = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert resp["result"]["protocolVersion"] == "2024-11-05"
        assert resp["result"]["serverInfo"]["name"] == "ragebot-mcp"

    def test_tools_list(self, server):
        resp = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        names = [t["name"] for t in resp["result"]["tools"]]
        for expected in ("ragebot_ask", "ragebot_search", "ragebot_save",
                         "ragebot_explain", "ragebot_status", "ragebot_export",
                         "ragebot_generate_docs", "ragebot_generate_tests", "ragebot_diff_explain"):
            assert expected in names

    def test_call_status(self, server):
        resp = server.handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                      "params": {"name": "ragebot_status", "arguments": {}}})
        assert resp["result"]["isError"] is False

    def test_call_file_tree(self, server):
        resp = server.handle_request({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                                      "params": {"name": "ragebot_file_tree", "arguments": {}}})
        assert resp["result"]["isError"] is False
        assert "main.py" in resp["result"]["content"][0]["text"]

    def test_call_search(self, server):
        resp = server.handle_request({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                                      "params": {"name": "ragebot_search",
                                                 "arguments": {"query": "hello", "search_type": "keyword"}}})
        assert resp["result"]["isError"] is False

    def test_unknown_method_returns_error(self, server):
        resp = server.handle_request({"jsonrpc": "2.0", "id": 9, "method": "not_a_method", "params": {}})
        assert "error" in resp

    def test_unknown_tool_returns_error(self, server):
        resp = server.handle_request({"jsonrpc": "2.0", "id": 10, "method": "tools/call",
                                      "params": {"name": "bad_tool", "arguments": {}}})
        assert resp["result"]["isError"] is True

    def test_notification_returns_none(self, server):
        resp = server.handle_request({"jsonrpc": "2.0", "method": "initialized", "params": {}})
        assert resp is None

    def test_ping(self, server):
        resp = server.handle_request({"jsonrpc": "2.0", "id": 11, "method": "ping", "params": {}})
        assert resp["result"] == {}
