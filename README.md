# 🤖 RageBot MCP

> **Intelligent Project Context Engine with full MCP Server support.**
> Index your codebase, query it in natural language, and expose it as tools to any AI client.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)
[![Typer](https://img.shields.io/badge/CLI-Typer-008080.svg)](https://typer.tiangolo.com/)
[![FAISS](https://img.shields.io/badge/Search-FAISS-blue.svg)](https://github.com/facebookresearch/faiss)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📦 Installation

To install RageBot as a package, run:

```bash
pip install ragebot
```

---

## ✨ Features

- 🔍 **Semantic Code Search**: Powered by FAISS and Sentence-Transformers for deep codebase understanding.
- 💬 **Interactive AI Chat**: Multi-turn persistent sessions with context preservation.
- 🤖 **Multi-Provider LLM**: Support for Google Gemini, Groq, and local Ollama models.
- 🔌 **Full MCP Server**: Expose your codebase as tools to Claude Desktop, Cursor, Zed, and more.
- 📖 **Code Intelligence**: Auto-generate documentation, unit tests, and symbol explanations.
- 📸 **Snapshot Management**: Save, list, and restore project index states instantly.
- 🔒 **Secure Key Storage**: API keys are stored in the OS keyring (macOS Keychain, Windows Credential Manager).
- 🎨 **Modern CLI**: Rich terminal output with interactive menus and progress indicators.

---

## 🚀 Quick Start

### 1. Authenticate
Configure your preferred AI provider:
```bash
# Interactive setup for Gemini, Groq, or Ollama
rage auth 
```

### 2. Initialize & Index
Prepare your project for analysis:
```bash
cd /path/to/your/project
rage init
rage save
```

### 3. Start Querying
Ask questions or enter the interactive REPL:
```bash
# Ask a quick question
rage ask "How does the authentication logic work?"

# Start interactive REPL
ragebot
```

---

## 📋 Command Reference

### Core Commands
| Command | Description |
|---|---|
| `rage init` | Initialize RageBot in the current directory. |
| `rage save` | Index the project and save a snapshot. |
| `rage ask` | Ask a one-shot question about the codebase. |
| `rage chat` | Start an interactive multi-turn chat session. |
| `rage search` | Perform a semantic search across files. |
| `rage explain` | Get a detailed explanation of a file or symbol. |
| `rage docs` | Generate Markdown documentation for a file. |
| `rage test` | Generate pytest test cases for a file. |
| `rage status` | Show project indexing and LLM connectivity status. |
| `rage context` | Show project overview (use `--tree` for file structure). |

### Management Commands
| Command | Description |
|---|---|
| `rage auth` | Manage API keys and active providers. |
| `rage config` | View or edit configuration settings. |
| `rage model` | Switch between available models for the active provider. |
| `rage snapshot` | List, restore, or delete project snapshots. |
| `rage history` | List and resume previous chat sessions. |

---

## 🔌 MCP Server

RageBot is a compliant **Model Context Protocol** server. You can use it as a toolset for AI IDEs and clients.

### Tools Provided:
- `ragebot_ask`: AI question & answer with citations.
- `ragebot_search`: Semantic/keyword search.
- `ragebot_save`: Index or re-index the project.
- `ragebot_explain`: Explain files or symbols.
- `ragebot_file_tree`: Get project structure.
- `ragebot_generate_docs`: Auto-generate documentation.
- `ragebot_generate_tests`: Auto-generate tests.
- `ragebot_apply_edit`: Apply natural language edits to files.

### Start the Server:
```bash
# Stdio transport (default)
ragebot-mcp-server --project /path/to/your/project

# SSE transport
ragebot-mcp-server --transport sse --port 8765 --project /path/to/your/project
```

---

## 📁 Project Structure

```
ragebot/
├── agents/             # Context builders for specific AI roles
├── auth/               # Secure provider authentication (Keyring)
├── core/               # Orchestrator, Scanner, and Config management
├── llm/                # LLM implementations (Gemini, Groq, Ollama)
├── mcp/                # MCP Server implementation (Stdio & SSE)
├── parsers/            # AST-based code and document parsers
├── search/             # Vector embeddings and FAISS retrieval
├── storage/            # SQLite database and Snapshot logic
└── utils/              # UI helpers, logging, and token utilities
```

---

## 🛠️ Development

If you want to contribute or run from source:

1. Clone the repository:
   ```bash
   git clone https://github.com/atharvrahate296/Ragebot-MCP
   cd Ragebot-MCP
   ```

2. Install in editable mode:
   ```bash
   pip install -r requirements.txt
   ```

3. Run tests:
   ```bash
    python ./tests/tests.py
   ```

---

`Contributions from all collaborators are welcome for the continued development of RageBot MCP.`

--- 

## 📄 License

MIT © Atharv Rahate
