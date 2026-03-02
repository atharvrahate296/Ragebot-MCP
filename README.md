# 🤖 RageBot MCP

> **Intelligent CLI-based Project Context Engine with full MCP Server support.**
> Index your codebase, query it in natural language, chat with it interactively, generate docs & tests — and expose all of it as MCP tools to any AI client (Claude Desktop, Cursor, Zed, Continue.dev).

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📁 Project Structure

```
ragebot-mcp/
├── ragebot/                        # Main Python package
│   ├── __init__.py
│   ├── cli.py                      # Typer CLI — all `rage` commands
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py               # Config manager + secure keyring storage
│   │   ├── engine.py               # Core orchestrator (scan→parse→embed→retrieve→answer)
│   │   ├── scanner.py              # Directory scanner & file classifier
│   │   └── watcher.py              # watchdog file-system watcher
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py                 # Abstract BaseLLMProvider interface
│   │   ├── gemini.py               # Google Gemini provider
│   │   ├── grok.py                 # xAI Grok provider (OpenAI-compatible API)
│   │   ├── noop.py                 # No-op provider (no key configured)
│   │   └── factory.py              # Resolves active provider from config
│   ├── mcp/
│   │   ├── __init__.py
│   │   └── server.py               # Full MCP JSON-RPC 2.0 server (stdio + SSE)
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── code_parser.py          # AST + regex parser (Python,JS,TS,Go,Rust,Java,C…)
│   │   └── doc_parser.py           # Document parser (PDF, DOCX, MD, TXT)
│   ├── search/
│   │   ├── __init__.py
│   │   ├── embedder.py             # Sentence-transformer embeddings + disk cache
│   │   └── retriever.py            # FAISS / cosine-similarity semantic search
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── db.py                   # SQLite layer (files, chunks, embeddings, chat history)
│   │   └── snapshot.py             # Snapshot create / restore / delete
│   ├── agents/
│   │   ├── __init__.py
│   │   └── context_builder.py      # Context packs for debug/docs/refactor/review/test
│   └── utils/
│       ├── __init__.py
│       ├── display.py              # Rich terminal output helpers
│       └── tokens.py               # tiktoken token counter + cost estimator
├── tests/
│   ├── __init__.py
│   └── test_ragebot.py             # Full pytest test suite (50+ tests)
├── .env.example                    # Example environment variables
├── .gitignore
├── deploy.md                       # Deployment guide (Claude Desktop, Docker, cloud…)
├── pyproject.toml                  # Modern Python packaging (PEP 517)
├── requirements.txt                # Core dependencies
├── requirements-full.txt           # Full dependencies (all optional features)
├── setup.py                        # Backward-compatible setup entry
└── README.md                       # This file
```

---

## ✨ Features at a Glance

| Feature | Description |
|---|---|
| 🗂 **Directory Scanning** | Recursive scan, respects `.gitignore` |
| 🔍 **Multi-language Parsing** | Python AST + regex for JS, TS, Go, Rust, Java, C/C++ |
| 📄 **Document Processing** | PDF, DOCX, Markdown, TXT |
| 🧠 **Semantic Search** | Vector embeddings via sentence-transformers + FAISS |
| 💡 **AI-Powered Answers** | Google Gemini or xAI Grok |
| 💬 **Interactive Chat** | Multi-turn persistent sessions with history |
| 📖 **Code Explanation** | Explain any file or function/class |
| 📝 **Doc Generation** | Auto-generate Markdown documentation |
| 🧪 **Test Generation** | Auto-generate pytest test suites |
| 🔀 **Diff Explanation** | Explain git diffs in plain English |
| 📦 **Agent Context Packs** | Optimised export for debug/docs/refactor/review/test agents |
| 📸 **Snapshots** | Save and restore project index states |
| 👁️ **File Watching** | Auto re-indexes on file changes |
| 🔒 **Secure Key Storage** | API keys in OS keyring — never in config files |
| 🔌 **Real MCP Server** | JSON-RPC 2.0 over stdio or HTTP/SSE |
| ⚙️ **Full Config System** | CLI config + env var overrides |

---

## 🚀 Quick Start

### 1. Install

```bash
git clone https://github.com/atharvrahate296/Ragebot-MCP
cd Ragebot-MCP

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Core + Gemini (recommended)
pip install -e ".[gemini]"

# Core + Grok
pip install -e ".[grok]"

# Everything (PDF, DOCX, FAISS, SSE server, file watching)
pip install -e ".[full]"
```

### 2. Authenticate

```bash
# Gemini — get key at https://aistudio.google.com/apikey
rage auth login gemini
# Prompted: Enter Gemini API key: ••••••••   (stored in OS keyring, never in a file)

# Grok — get key at https://console.x.ai
rage auth login grok

# Check status
rage auth status

# Switch provider
rage auth switch gemini
```

### 3. Index your project

```bash
cd /your/project
rage init
rage save
```

### 4. Start using it

```bash
rage ask "Where is the login logic?"
rage chat
rage explain src/auth.py --symbol login
rage docs src/auth.py --output docs/auth.md
rage test src/auth.py --output tests/test_auth.py
rage diff --staged
rage status
```

---

## 📋 Complete Command Reference

### Core Commands

| Command | Description |
|---|---|
| `rage init [path]` | Initialise RageBot in a project directory |
| `rage save [path]` | Index project, save snapshot (`--full` to re-index all) |
| `rage ask <query>` | One-shot AI question (`--mode minimal\|smart\|full`) |
| `rage chat` | Interactive multi-turn chat (`--session` to resume) |
| `rage search <query>` | File search (`--type semantic\|keyword\|hybrid`) |
| `rage explain <file>` | Explain file or symbol (`--symbol fn_name`) |
| `rage docs <file>` | Generate Markdown docs (`--output file.md`) |
| `rage test <file>` | Generate pytest tests (`--output test_file.py`) |
| `rage diff` | Explain git diff (`--staged`, `--head`, or pipe diff) |
| `rage context` | Show project info (`--tree`, `--summary`, `--file path`) |
| `rage export <type>` | Export context pack: `debug\|docs\|refactor\|review\|test` |
| `rage status` | Index stats + LLM health |
| `rage watch` | Auto re-index on changes (`--debounce N`) |
| `rage clean` | Clean cache (`--all` to remove everything) |
| `rage version` | Version info |

### Auth Sub-commands

| Command | Description |
|---|---|
| `rage auth login <gemini\|grok>` | Store API key in OS keyring |
| `rage auth logout <gemini\|grok>` | Remove key from keyring |
| `rage auth status` | Show which providers are authenticated |
| `rage auth switch <gemini\|grok\|none>` | Switch active provider |

### Config Sub-commands

| Command | Description |
|---|---|
| `rage config show` | Show all settings |
| `rage config set <key> <value>` | Set a value (non-secrets only) |
| `rage config get <key>` | Get a single value |
| `rage config reset` | Reset to defaults |

### Snapshot Sub-commands

| Command | Description |
|---|---|
| `rage snapshots list` | List saved snapshots |
| `rage snapshots restore <name>` | Restore a snapshot |
| `rage snapshots delete <name>` | Delete a snapshot |

### History Sub-commands

| Command | Description |
|---|---|
| `rage history list` | List all chat sessions |
| `rage history show <session_id>` | Show messages in a session |
| `rage history delete <session_id>` | Delete a session |

### MCP Sub-commands

| Command | Description |
|---|---|
| `rage mcp start` | Start MCP server (`--transport stdio\|sse`) |
| `rage mcp config` | Configure MCP server defaults |

---

## 🤖 LLM Providers

### Google Gemini

```bash
# Get key: https://aistudio.google.com/apikey
rage auth login gemini

# Configure model
rage config set gemini_model gemini-1.5-pro    # default: gemini-1.5-flash
```

### xAI Grok

```bash
# Get key: https://console.x.ai
rage auth login grok

# Configure model
rage config set grok_model grok-3              # default: grok-3-mini
```

> **Note:** Grok uses the OpenAI-compatible REST API at `https://api.x.ai/v1` — no extra SDK needed beyond `openai`.

### No LLM (context retrieval only)

```bash
rage auth switch none
# rage ask still retrieves and shows context, but won't generate AI answers
```

---

## 🔌 MCP Server

RageBot is a **real MCP server** with 10 tools:

| MCP Tool | What it does |
|---|---|
| `ragebot_ask` | AI question → answer with source citations |
| `ragebot_search` | Semantic / keyword / hybrid file search |
| `ragebot_save` | Index or re-index the project |
| `ragebot_explain` | Explain a file or named symbol |
| `ragebot_file_tree` | Return the project directory tree |
| `ragebot_status` | Index statistics and LLM health |
| `ragebot_export` | Export agent context pack |
| `ragebot_generate_docs` | Generate Markdown docs for a file |
| `ragebot_generate_tests` | Generate pytest tests for a file |
| `ragebot_diff_explain` | Explain a git diff patch |

### Quick start (stdio — for Claude Desktop / Cursor)

```bash
rage mcp start --transport stdio --project /path/to/project
```

### Remote server (SSE)

```bash
rage mcp start --transport sse --host 0.0.0.0 --port 8765 --project /path/to/project
```

### Claude Desktop config

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ragebot": {
      "command": "/path/to/.venv/bin/python",
      "args": [
        "-m", "ragebot.mcp.server",
        "--project", "/path/to/your/project",
        "--transport", "stdio"
      ]
    }
  }
}
```

> **Full deployment guide:** see [`deploy.md`](./deploy.md) — covers Claude Desktop, Cursor, Zed, Continue.dev, Docker, Railway, Fly.io, systemd, and Nginx/TLS.

---

## ⚙️ Configuration Reference

Settings live at `~/.config/ragebot/config.json`. API keys are **never** stored there.

| Key | Default | Description |
|---|---|---|
| `llm_provider` | `gemini` | Active LLM: `gemini` \| `grok` \| `none` |
| `gemini_model` | `gemini-1.5-flash` | Gemini model name |
| `grok_model` | `grok-3-mini` | Grok model name |
| `embedding_model` | `all-MiniLM-L6-v2` | Sentence-transformer model |
| `default_top_k` | `5` | Context chunks per query |
| `chunk_size` | `512` | Tokens per chunk |
| `chunk_overlap` | `64` | Overlap between chunks |
| `max_file_size_kb` | `500` | Skip files larger than this |
| `max_chunks_per_file` | `20` | Cap chunks indexed per file |
| `index_depth` | `10` | Max directory recursion depth |
| `ignore_patterns` | `.git,node_modules,…` | Comma-separated glob patterns to skip |
| `default_mode` | `smart` | Answer mode: `minimal` \| `smart` \| `full` |
| `max_answer_tokens` | `1000` | Max LLM response tokens |
| `mcp_transport` | `stdio` | MCP transport: `stdio` \| `sse` |
| `mcp_host` | `127.0.0.1` | SSE bind host |
| `mcp_port` | `8765` | SSE bind port |

### Environment variables

| Variable | Config key |
|---|---|
| `GEMINI_API_KEY` | `gemini_api_key` (keyring) |
| `GROK_API_KEY` | `grok_api_key` (keyring) |
| `RAGEBOT_LLM_PROVIDER` | `llm_provider` |
| `RAGEBOT_EMBEDDING_MODEL` | `embedding_model` |
| `RAGEBOT_MCP_TRANSPORT` | `mcp_transport` |
| `RAGEBOT_MCP_HOST` | `mcp_host` |
| `RAGEBOT_MCP_PORT` | `mcp_port` |

---

## 💬 Chat Session Commands

Once inside `rage chat`, use these slash commands:

| Command | Action |
|---|---|
| `/exit` or `/quit` | End the session |
| `/history` | Show last 10 messages |
| `/clear` | Delete this session's history |
| `/export [filename.json]` | Export chat to JSON |

---

## 🔒 Security

- API keys use the **OS keyring** — macOS Keychain, GNOME Keyring, or Windows Credential Manager
- Keys are **never** written to `config.json`, `.env` files, or logs
- `rage config show` displays keys masked as `********abcd`
- `rage config set` will refuse to set secret keys and redirect you to `rage auth login`
- If keyring is unavailable, set keys via environment variables only (`GEMINI_API_KEY`)

---

## 🛠️ Development

```bash
# Install dev dependencies
pip install -e ".[dev,full]"

# Run tests
pytest tests/ -v

# With coverage report
pytest tests/ -v --cov=ragebot --cov-report=html

# Lint
ruff check ragebot/
black ragebot/

# Type check
mypy ragebot/
```

---

## 🏗️ Architecture Overview

```
rage CLI
   └─► RageBotEngine
          ├── DirectoryScanner     recursive scan, .gitignore logic, file classifier
          ├── CodeParser           Python AST + regex → functions, classes, imports
          ├── DocumentParser       PDF/DOCX/MD/TXT → clean text chunks
          ├── Embedder             sentence-transformers → float vectors (disk cached)
          ├── ContextRetriever     FAISS / cosine similarity → top-k relevant chunks
          ├── Database (SQLite)    files · chunks · embeddings · chat history
          ├── SnapshotManager      versioned DB copies
          ├── LLM Provider         Gemini or Grok (resolved by factory)
          └── ContextBuilder       agent-specific context packs

ragebot.mcp.server
   ├── stdio transport   JSON-RPC 2.0 over stdin/stdout (for desktop clients)
   ├── SSE transport     FastAPI + uvicorn HTTP (for remote / cloud clients)
   └── 10 MCP tools      ask · search · save · explain · file_tree · status
                         export · generate_docs · generate_tests · diff_explain
```

---

## 📄 License

MIT © RageBot Team

---

## 🔗 Links

| Resource | URL |
|---|---|
| Deployment Guide | [`deploy.md`](./deploy.md) |
| MCP Protocol Spec | [modelcontextprotocol.io](https://modelcontextprotocol.io) |
| Gemini API Keys | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| Grok API Keys | [console.x.ai](https://console.x.ai) |
| sentence-transformers | [sbert.net](https://www.sbert.net) |
