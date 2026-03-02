"""
RageBot MCP Server
───────────────────
Implements the Model Context Protocol (MCP) so that any MCP-compatible
AI client (Claude Desktop, Cursor, Zed, Continue.dev …) can call RageBot
as a set of tools.

Transport options:
  stdio  — default; the client spawns this process and pipes JSON-RPC over stdin/stdout
  sse    — HTTP Server-Sent Events; client connects via HTTP to a long-lived server

Usage (stdio):
    python -m ragebot.mcp.server --project /path/to/project

Usage (SSE):
    python -m ragebot.mcp.server --transport sse --host 0.0.0.0 --port 8765 --project /path/to/project
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from ragebot.core.config  import ConfigManager
from ragebot.core.engine  import RageBotEngine

logger = logging.getLogger("ragebot.mcp")

# ── MCP Protocol constants ────────────────────────────────────────────────────
PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {
    "name":    "ragebot-mcp",
    "version": "1.0.0",
}

# ── Tool definitions (JSON Schema) ────────────────────────────────────────────
TOOLS: list[dict] = [
    {
        "name": "ragebot_ask",
        "description": (
            "Ask a natural language question about the indexed project. "
            "Returns an AI-generated answer with source file citations."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query":  {"type": "string",  "description": "The question to ask"},
                "mode":   {"type": "string",  "enum": ["minimal","smart","full"], "default": "smart"},
                "top_k":  {"type": "integer", "default": 5, "description": "Max context chunks"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "ragebot_search",
        "description": "Search project files by keyword, semantic, or hybrid search.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query":       {"type": "string"},
                "search_type": {"type": "string", "enum": ["semantic","keyword","hybrid"], "default": "semantic"},
                "top_k":       {"type": "integer", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "ragebot_save",
        "description": "Index (or re-index) the project directory and save a snapshot.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "incremental":     {"type": "boolean", "default": True},
                "snapshot_name":   {"type": "string"},
            },
        },
    },
    {
        "name": "ragebot_explain",
        "description": "Get a detailed explanation of a source file or a specific function/class within it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative path to the file"},
                "symbol":    {"type": "string", "description": "Optional: function or class name to explain"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "ragebot_file_tree",
        "description": "Return the project directory tree as a text string.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ragebot_status",
        "description": "Return the current indexing status and project statistics.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "ragebot_export",
        "description": "Export an optimised context pack for a specific AI agent role.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_type": {"type": "string", "enum": ["debug","docs","refactor","review","test"]},
                "focus":      {"type": "string", "description": "Optional file or directory filter"},
            },
            "required": ["agent_type"],
        },
    },
    {
        "name": "ragebot_generate_docs",
        "description": "Generate Markdown documentation for a specific source file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "ragebot_generate_tests",
        "description": "Generate pytest test cases for a specific source file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "ragebot_diff_explain",
        "description": "Explain a git diff patch in plain English.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "diff": {"type": "string", "description": "The raw git diff text"},
            },
            "required": ["diff"],
        },
    },
]


class RageBotMCPServer:
    """Handles the MCP JSON-RPC 2.0 protocol over any transport."""

    def __init__(self, project_path: Path, config: ConfigManager) -> None:
        self.engine = RageBotEngine(project_path=project_path, config=config)
        self._initialized = False

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def handle_request(self, request: dict) -> Optional[dict]:
        """Process one JSON-RPC request and return a response dict (or None for notifications)."""
        method  = request.get("method", "")
        req_id  = request.get("id")
        params  = request.get("params", {})

        handlers = {
            "initialize":          self._handle_initialize,
            "initialized":         self._handle_notification,
            "tools/list":          self._handle_tools_list,
            "tools/call":          self._handle_tools_call,
            "ping":                self._handle_ping,
            "notifications/cancelled": self._handle_notification,
        }

        handler = handlers.get(method)
        if handler is None:
            if req_id is None:
                return None                         # Unknown notification — silently ignore
            return self._error(req_id, -32601, f"Method not found: {method}")

        try:
            result = handler(params)
            if req_id is None:
                return None                         # Notification — no response
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as exc:
            logger.exception("Error handling %s", method)
            if req_id is None:
                return None
            return self._error(req_id, -32603, str(exc))

    # ── Protocol handlers ─────────────────────────────────────────────────────

    def _handle_initialize(self, params: dict) -> dict:
        self._initialized = True
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo":      SERVER_INFO,
            "capabilities": {
                "tools": {"listChanged": False},
            },
        }

    def _handle_notification(self, params: dict) -> dict:
        return {}

    def _handle_ping(self, params: dict) -> dict:
        return {}

    def _handle_tools_list(self, params: dict) -> dict:
        return {"tools": TOOLS}

    def _handle_tools_call(self, params: dict) -> dict:
        tool_name = params.get("name", "")
        args      = params.get("arguments", {})

        dispatchers = {
            "ragebot_ask":            self._tool_ask,
            "ragebot_search":         self._tool_search,
            "ragebot_save":           self._tool_save,
            "ragebot_explain":        self._tool_explain,
            "ragebot_file_tree":      self._tool_file_tree,
            "ragebot_status":         self._tool_status,
            "ragebot_export":         self._tool_export,
            "ragebot_generate_docs":  self._tool_generate_docs,
            "ragebot_generate_tests": self._tool_generate_tests,
            "ragebot_diff_explain":   self._tool_diff_explain,
        }

        fn = dispatchers.get(tool_name)
        if fn is None:
            return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}]}

        try:
            result = fn(args)
            return {
                "isError": False,
                "content": [{"type": "text", "text": json.dumps(result, indent=2) if isinstance(result, dict) else str(result)}],
            }
        except Exception as exc:
            logger.exception("Tool %s failed", tool_name)
            return {"isError": True, "content": [{"type": "text", "text": str(exc)}]}

    # ── Tool implementations ──────────────────────────────────────────────────

    def _tool_ask(self, args: dict) -> dict:
        return self.engine.ask(
            query=args["query"],
            mode=args.get("mode", "smart"),
            top_k=int(args.get("top_k", 5)),
        )

    def _tool_search(self, args: dict) -> list:
        return self.engine.search(
            query=args["query"],
            search_type=args.get("search_type", "semantic"),
            top_k=int(args.get("top_k", 10)),
        )

    def _tool_save(self, args: dict) -> dict:
        return self.engine.save(
            incremental=bool(args.get("incremental", True)),
            snapshot_name=args.get("snapshot_name"),
        )

    def _tool_explain(self, args: dict) -> dict:
        return self.engine.explain(
            file_path=args["file_path"],
            symbol=args.get("symbol"),
        )

    def _tool_file_tree(self, args: dict) -> dict:
        return self.engine.get_file_tree()

    def _tool_status(self, args: dict) -> dict:
        return self.engine.get_status()

    def _tool_export(self, args: dict) -> dict:
        return self.engine.export_context(
            agent_type=args["agent_type"],
            focus=args.get("focus"),
        )

    def _tool_generate_docs(self, args: dict) -> str:
        return self.engine.generate_docs(args["file_path"])

    def _tool_generate_tests(self, args: dict) -> str:
        return self.engine.generate_tests(args["file_path"])

    def _tool_diff_explain(self, args: dict) -> str:
        return self.engine.diff_explain(args["diff"])

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _error(req_id: Any, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


# ── Transports ────────────────────────────────────────────────────────────────

def run_stdio(server: RageBotMCPServer) -> None:
    """Run the MCP server over stdin/stdout (newline-delimited JSON-RPC)."""
    logger.info("RageBot MCP server started (stdio transport)")
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            request = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": f"Parse error: {exc}"}}
            print(json.dumps(response), flush=True)
            continue

        response = server.handle_request(request)
        if response is not None:
            print(json.dumps(response), flush=True)


def run_sse(server: RageBotMCPServer, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the MCP server over HTTP/SSE."""
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import StreamingResponse, JSONResponse
        import uvicorn
        import asyncio
    except ImportError as exc:
        raise RuntimeError(
            "SSE transport requires: pip install fastapi uvicorn\n"
            f"Original error: {exc}"
        ) from exc

    sse_app = FastAPI(title="RageBot MCP Server")
    _sessions: dict[str, list[dict]] = {}

    @sse_app.get("/health")
    async def health():
        return {"status": "ok", "server": SERVER_INFO}

    @sse_app.post("/mcp")
    async def mcp_endpoint(req: Request):
        body    = await req.json()
        response = server.handle_request(body)
        return JSONResponse(content=response or {})

    @sse_app.get("/sse/{session_id}")
    async def sse_stream(session_id: str):
        """SSE endpoint: client subscribes, server pushes events."""
        _sessions[session_id] = []

        async def event_generator():
            yield f"data: {json.dumps({'type':'connected','session':session_id})}\n\n"
            last_idx = 0
            while True:
                msgs = _sessions.get(session_id, [])
                for msg in msgs[last_idx:]:
                    yield f"data: {json.dumps(msg)}\n\n"
                    last_idx += 1
                await asyncio.sleep(0.1)

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @sse_app.post("/sse/{session_id}/message")
    async def sse_message(session_id: str, req: Request):
        body     = await req.json()
        response = server.handle_request(body)
        if response:
            _sessions.setdefault(session_id, []).append(response)
        return JSONResponse(content={"ok": True})

    logger.info("RageBot MCP SSE server on http://%s:%s", host, port)
    uvicorn.run(sse_app, host=host, port=port, log_level="warning")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="RageBot MCP Server")
    parser.add_argument("--project",   default=".", help="Project directory to serve")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse"])
    parser.add_argument("--host",      default="127.0.0.1")
    parser.add_argument("--port",      type=int, default=8765)
    parser.add_argument("--log-level", default="WARNING")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.WARNING))

    config       = ConfigManager()
    project_path = Path(args.project).resolve()
    server       = RageBotMCPServer(project_path=project_path, config=config)

    # Auto-init if not yet done
    if not (project_path / ".ragebot" / "ragebot.db").exists():
        server.engine.initialize()

    if args.transport == "sse":
        run_sse(server, host=args.host, port=args.port)
    else:
        run_stdio(server)


if __name__ == "__main__":
    main()
