# 🚀 RageBot MCP — Deployment Guide

This guide covers every way to deploy RageBot MCP so any MCP-compatible AI client
(Claude Desktop, Cursor, Zed, Continue.dev, Cline, …) can use it as a set of tools.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installation](#2-installation)
3. [Authenticating with Gemini or Grok](#3-authenticating)
4. [Transport Options: stdio vs SSE](#4-transports)
5. [Claude Desktop Integration](#5-claude-desktop)
6. [Cursor Integration](#6-cursor)
7. [Zed Integration](#7-zed)
8. [Continue.dev Integration](#8-continuedev)
9. [Docker Deployment (SSE)](#9-docker)
10. [Remote / Cloud Deployment (SSE)](#10-remote)
11. [Running as a systemd Service](#11-systemd)
12. [Environment Variables Reference](#12-env-vars)
13. [Verifying the Server](#13-verifying)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10 or later |
| pip    | 23+ |
| OS     | macOS, Linux, Windows (WSL recommended) |

---

## 2. Installation

### Option A — Install from source (recommended for development)

```bash
git clone https://github.com/ragebot/mcp
cd mcp

# Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Core + your chosen LLM
pip install -e ".[gemini]"       # for Gemini
pip install -e ".[grok]"         # for Grok
pip install -e ".[full]"         # everything
```

### Option B — Install from PyPI (when published)

```bash
pip install "ragebot-mcp[gemini]"    # Gemini support
pip install "ragebot-mcp[grok]"      # Grok support
pip install "ragebot-mcp[full]"      # All features
```

### Verify installation

```bash
rage version
```

---

## 3. Authenticating

API keys are **stored in the OS keyring** (not in config files).

### Gemini (Google AI)

1. Get your API key at <https://aistudio.google.com/apikey>
2. Store it securely:

```bash
rage auth login gemini
# You will be prompted: Enter Gemini API key: ••••••••
```

### Grok (xAI)

1. Get your API key at <https://console.x.ai>
2. Store it securely:

```bash
rage auth login grok
# You will be prompted: Enter Grok API key: ••••••••
```

### Verify auth

```bash
rage auth status
```

### Switch provider

```bash
rage auth switch gemini
rage auth switch grok
```

### Remove a key

```bash
rage auth logout gemini
```

---

## 4. Transports

RageBot supports two MCP transports:

| Transport | When to use |
|---|---|
| **stdio** | Client spawns the process locally. Zero network setup. Recommended for desktop clients. |
| **SSE** | HTTP server; client connects over the network. Required for remote/cloud deployments. |

---

## 5. Claude Desktop Integration (stdio)

**Recommended for local use.**

### Step 1 — Find the Claude Desktop config file

| OS | Path |
|---|---|
| macOS   | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux   | `~/.config/Claude/claude_desktop_config.json` |

### Step 2 — Add RageBot to `mcpServers`

```json
{
  "mcpServers": {
    "ragebot": {
      "command": "/path/to/.venv/bin/python",
      "args": [
        "-m", "ragebot.mcp.server",
        "--project", "/path/to/your/project",
        "--transport", "stdio"
      ],
      "env": {
        "GEMINI_API_KEY": "your-key-here"
      }
    }
  }
}
```

> **Tip:** If you stored the key in keyring via `rage auth login`, you can omit the `env` block entirely — the server reads from keyring automatically.

### Step 3 — Index your project

```bash
cd /path/to/your/project
rage init
rage save
```

### Step 4 — Restart Claude Desktop

The RageBot tools (`ragebot_ask`, `ragebot_search`, etc.) will appear in Claude's tool list.

---

## 6. Cursor Integration (stdio)

Open **Cursor → Settings → MCP** and add:

```json
{
  "mcpServers": {
    "ragebot": {
      "command": "python",
      "args": ["-m", "ragebot.mcp.server", "--project", "${workspaceFolder}"]
    }
  }
}
```

Or add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "ragebot": {
      "command": "python",
      "args": ["-m", "ragebot.mcp.server", "--project", "."]
    }
  }
}
```

---

## 7. Zed Integration (stdio)

Add to `~/.config/zed/settings.json`:

```json
{
  "context_servers": {
    "ragebot": {
      "command": {
        "path": "python",
        "args": ["-m", "ragebot.mcp.server", "--project", "/path/to/project"]
      }
    }
  }
}
```

---

## 8. Continue.dev Integration (stdio)

Add to `~/.continue/config.json`:

```json
{
  "experimental": {
    "modelContextProtocolServers": [
      {
        "transport": {
          "type": "stdio",
          "command": "python",
          "args": ["-m", "ragebot.mcp.server", "--project", "/path/to/project"]
        }
      }
    ]
  }
}
```

---

## 9. Docker Deployment (SSE)

### Build the image

```bash
# In the ragebot directory
docker build -t ragebot-mcp .
```

### Dockerfile (create this in project root)

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir ".[full]"

EXPOSE 8765

ENV RAGEBOT_MCP_TRANSPORT=sse
ENV RAGEBOT_MCP_HOST=0.0.0.0
ENV RAGEBOT_MCP_PORT=8765

ENTRYPOINT ["python", "-m", "ragebot.mcp.server", \
            "--transport", "sse", \
            "--host", "0.0.0.0", \
            "--port", "8765"]
```

### Run with Docker

```bash
docker run -d \
  --name ragebot \
  -p 8765:8765 \
  -v /path/to/your/project:/project:ro \
  -e GEMINI_API_KEY=your-key \
  ragebot-mcp \
  --project /project
```

### Docker Compose

```yaml
version: "3.9"
services:
  ragebot:
    build: .
    ports:
      - "8765:8765"
    volumes:
      - /path/to/project:/project:ro
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - RAGEBOT_LLM_PROVIDER=gemini
    command: >
      python -m ragebot.mcp.server
      --transport sse
      --host 0.0.0.0
      --port 8765
      --project /project
    restart: unless-stopped
```

```bash
GEMINI_API_KEY=your-key docker compose up -d
```

---

## 10. Remote / Cloud Deployment (SSE)

### Start the SSE server

```bash
# On the remote machine
pip install "ragebot-mcp[full]"
export GEMINI_API_KEY=your-key
export RAGEBOT_LLM_PROVIDER=gemini

cd /path/to/project
rage init && rage save

python -m ragebot.mcp.server \
  --transport sse \
  --host 0.0.0.0 \
  --port 8765 \
  --project .
```

### Connect from Claude Desktop (SSE transport)

```json
{
  "mcpServers": {
    "ragebot-remote": {
      "url": "http://your-server-ip:8765/sse/my-session",
      "transport": "sse"
    }
  }
}
```

### Secure with Nginx + TLS (production)

```nginx
server {
    listen 443 ssl;
    server_name ragebot.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/ragebot.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ragebot.yourdomain.com/privkey.pem;

    location / {
        proxy_pass         http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade    $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host       $host;
        proxy_buffering    off;           # Required for SSE
        proxy_cache        off;
        proxy_read_timeout 86400s;        # Long-lived SSE connections
    }
}
```

Then in Claude Desktop config:

```json
{
  "mcpServers": {
    "ragebot-remote": {
      "url": "https://ragebot.yourdomain.com/sse/my-session"
    }
  }
}
```

### Deploy to Railway / Render / Fly.io

#### Railway

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login

# Create project
railway new ragebot-mcp
railway up

# Set secrets
railway variables set GEMINI_API_KEY=your-key
railway variables set RAGEBOT_LLM_PROVIDER=gemini
railway variables set RAGEBOT_MCP_TRANSPORT=sse
```

Add `railway.json`:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": { "builder": "NIXPACKS" },
  "deploy": {
    "startCommand": "python -m ragebot.mcp.server --transport sse --host 0.0.0.0 --port $PORT --project /app/project",
    "healthcheckPath": "/health"
  }
}
```

#### Fly.io

```bash
fly launch --name ragebot-mcp
fly secrets set GEMINI_API_KEY=your-key
fly deploy
```

`fly.toml`:

```toml
app = "ragebot-mcp"
primary_region = "sjc"

[build]
  dockerfile = "Dockerfile"

[[services]]
  internal_port = 8765
  protocol = "tcp"
  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

[env]
  RAGEBOT_MCP_TRANSPORT = "sse"
  RAGEBOT_MCP_HOST = "0.0.0.0"
  RAGEBOT_MCP_PORT = "8765"
```

---

## 11. Running as a systemd Service (Linux)

Create `/etc/systemd/system/ragebot-mcp.service`:

```ini
[Unit]
Description=RageBot MCP Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/myproject
Environment=GEMINI_API_KEY=your-key-here
Environment=RAGEBOT_LLM_PROVIDER=gemini
ExecStart=/home/ubuntu/.venv/bin/python -m ragebot.mcp.server \
          --transport sse --host 0.0.0.0 --port 8765 --project .
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable ragebot-mcp
sudo systemctl start ragebot-mcp
sudo systemctl status ragebot-mcp
```

---

## 12. Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `GROK_API_KEY` | — | xAI Grok API key |
| `RAGEBOT_LLM_PROVIDER` | `gemini` | Active LLM: `gemini` \| `grok` \| `none` |
| `RAGEBOT_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model name |
| `RAGEBOT_MCP_TRANSPORT` | `stdio` | `stdio` or `sse` |
| `RAGEBOT_MCP_HOST` | `127.0.0.1` | SSE bind host |
| `RAGEBOT_MCP_PORT` | `8765` | SSE bind port |

---

## 13. Verifying the Server

### stdio — quick smoke test

```bash
cd /path/to/project
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | \
  python -m ragebot.mcp.server --project .
```

Expected output:

```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","serverInfo":{"name":"ragebot-mcp","version":"1.0.0"},"capabilities":{"tools":{"listChanged":false}}}}
```

### SSE — health check

```bash
curl http://localhost:8765/health
# {"status":"ok","server":{"name":"ragebot-mcp","version":"1.0.0"}}
```

### List tools via SSE

```bash
curl -s -X POST http://localhost:8765/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | python3 -m json.tool
```

### Ask a question via SSE

```bash
curl -s -X POST http://localhost:8765/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0","id":3,"method":"tools/call",
    "params":{"name":"ragebot_ask","arguments":{"query":"What does main.py do?"}}
  }' | python3 -m json.tool
```

---

## 14. Troubleshooting

### `rage` command not found

```bash
# Make sure your venv is active and the package is installed
source .venv/bin/activate
pip install -e .
which rage
```

### `keyring` not available (key storage warning)

```bash
pip install keyring
# On Linux you may also need a backend:
pip install secretstorage dbus-python   # GNOME keyring
# Or use environment variables as a fallback:
export GEMINI_API_KEY=your-key
```

### Sentence-transformers slow on first run

This is normal — the model downloads (~90 MB) on first use and is cached in `~/.cache/torch/`.

### SSE connection drops immediately

Make sure `proxy_buffering off` is set in Nginx, and that your load balancer supports long-lived HTTP connections. Increase `proxy_read_timeout` to at least 3600s.

### Claude Desktop doesn't see the tools

1. Check the config file path for your OS (section 5).
2. Restart Claude Desktop completely (not just reload).
3. Check the MCP server logs — run `rage mcp start --log-level DEBUG` manually and paste the same command into the config.

### `ModuleNotFoundError: ragebot`

Make sure you installed in editable mode (`pip install -e .`) inside the same virtualenv that the `command` in your MCP config points to.

---

## Quick Reference Card

```
# First time setup
git clone https://github.com/ragebot/mcp && cd mcp
python -m venv .venv && source .venv/bin/activate
pip install -e ".[gemini]"
rage auth login gemini

# Index a project
cd /your/project
rage init
rage save

# Use from CLI
rage ask "Where is the login logic?"
rage chat
rage explain src/auth.py --symbol login
rage docs src/auth.py --output docs/auth.md
rage test src/auth.py --output tests/test_auth.py

# Start as MCP server (for Claude Desktop)
rage mcp start --transport stdio --project .

# Start as remote MCP server
rage mcp start --transport sse --host 0.0.0.0 --port 8765 --project .
```
