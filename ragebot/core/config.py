"""
RageBot Configuration Manager (Updated)
────────────────────────────────────────
Non-secret settings  →  ~/.config/ragebot/config.json
API keys (secrets)   →  OS keyring (macOS Keychain / GNOME Keyring / Windows Credential Manager)
                        Fallback: ~/.config/ragebot/.secrets  (chmod 600, never committed)

Changes in this version:
✓ Added Ollama configuration support
✓ Added Ollama environment variable mappings
✓ Extended provider support (gemini, groq, ollama)
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────
CONFIG_DIR   = Path.home() / ".config" / "ragebot"
CONFIG_FILE  = CONFIG_DIR / "config.json"
SECRETS_FILE = CONFIG_DIR / ".secrets"
KEYRING_SERVICE = "ragebot-mcp"

# Keys that must never appear in config.json
_SECRET_KEYS: set[str] = {"gemini_api_key", "groq_api_key"}

# Env-var → config-key mapping
_ENV_MAP: dict[str, str] = {
    "RAGEBOT_MCP_TRANSPORT":         "mcp_transport",
    "RAGEBOT_MCP_HOST":              "mcp_host",
    "RAGEBOT_MCP_PORT":              "mcp_port",
    "RAGEBOT_CONTEXT_WINDOW_TURNS":  "context_window_turns",
    "RAGEBOT_CONTEXT_CACHE_ENABLED": "context_cache_enabled",
    "RAGEBOT_OLLAMA_BASE_URL":       "ollama_base_url",
}

# ── Non-secret defaults ───────────────────────────────────────────────────────
DEFAULTS: dict[str, str] = {
    # LLM
    "llm_provider":        "gemini",        # gemini | groq | ollama | none
    "gemini_model":        "gemini-2.0-flash",
    "groq_model":          "openai/gpt-oss-120b",
    "groq_base_url":       "https://api.groq.com/openai/v1",
    "ollama_model":        "llama3",
    "ollama_base_url":     "http://localhost:11434",
    # Embeddings
    "embedding_model":     "all-MiniLM-L6-v2",
    "embedding_batch_size":"32",
    # Indexing
    "default_top_k":       "5",
    "max_file_size_kb":    "500",
    "max_chunks_per_file": "20",
    "chunk_size":          "512",
    "chunk_overlap":       "64",
    "index_depth":         "10",
    "ignore_patterns":     ".git,node_modules,__pycache__,.venv,venv,env,ENV,dist,build,.DS_Store,*.pyc,*.egg-info,.ragebot,.pytest_cache,.mypy_cache,.ruff_cache,.tox,.nox",
    # Output
    "default_mode":        "smart",         # minimal | smart | full
    "output_format":       "rich",
    "max_answer_tokens":   "1000",
    # Features
    "auto_watch":          "false",
    "show_token_usage":    "true",
    "color_theme":         "default",
    # MCP server
    "mcp_host":            "127.0.0.1",
    "mcp_port":            "8765",
    "mcp_transport":       "stdio",
    # Context & Retrieval
    "context_window_turns":  "3",
    "context_cache_enabled": "true",
}


# ── Keyring helpers ───────────────────────────────────────────────────────────

def _keyring_available() -> bool:
    try:
        import keyring                                          # type: ignore
        keyring.get_keyring()
        return True
    except Exception:
        return False


def _keyring_get(key: str) -> str:
    try:
        import keyring                                          # type: ignore
        return keyring.get_password(KEYRING_SERVICE, key) or ""
    except Exception:
        return ""


def _keyring_set(key: str, value: str) -> bool:
    try:
        import keyring                                          # type: ignore
        keyring.set_password(KEYRING_SERVICE, key, value)
        return True
    except Exception:
        return False


def _keyring_delete(key: str) -> bool:
    try:
        import keyring                                          # type: ignore
        keyring.delete_password(KEYRING_SERVICE, key)
        return True
    except Exception:
        return False


# ── Secrets-file helpers (chmod-600 fallback) ─────────────────────────────────

def _secrets_file_read() -> dict[str, str]:
    if not SECRETS_FILE.exists():
        return {}
    try:
        data: dict[str, str] = {}
        for line in SECRETS_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            data[k.strip().lower()] = v.strip()
        return data
    except Exception:
        return {}


def _secrets_file_write(key: str, value: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    current = _secrets_file_read()
    current[key] = value
    lines = [f"{k}={v}" for k, v in current.items()]
    SECRETS_FILE.write_text("\n".join(lines) + "\n")
    try:
        SECRETS_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass


def _secrets_file_delete(key: str) -> bool:
    current = _secrets_file_read()
    if key not in current:
        return False
    del current[key]
    lines = [f"{k}={v}" for k, v in current.items()]
    SECRETS_FILE.write_text("\n".join(lines) + "\n")
    return True


# ── ConfigManager ─────────────────────────────────────────────────────────────

class ConfigManager:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._load()

    # ── Load ──────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        self._data = dict(DEFAULTS)

        if CONFIG_FILE.exists():
            try:
                stored = json.loads(CONFIG_FILE.read_text())
                safe   = {k: v for k, v in stored.items() if k not in _SECRET_KEYS}
                self._data.update(safe)
            except Exception:
                pass

        ig = self._data.get("ignore_patterns", "")
        if ".ragebot" not in ig:
            self._data["ignore_patterns"] = ig.rstrip(",") + ",.ragebot"

        for env_key, cfg_key in _ENV_MAP.items():
            val = os.environ.get(env_key)
            if val:
                self._data[cfg_key] = val

    def _save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        safe = {k: v for k, v in self._data.items() if k not in _SECRET_KEYS}
        CONFIG_FILE.write_text(json.dumps(safe, indent=2))

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        if key in _SECRET_KEYS:
            kr_val = _keyring_get(key)
            if kr_val:
                return kr_val
            sf_val = _secrets_file_read().get(key, "")
            if sf_val:
                return sf_val
            return default or ""
        return self._data.get(key, default)

    def set(self, key: str, value: str) -> dict[str, str]:
        if key in _SECRET_KEYS:
            if _keyring_available() and _keyring_set(key, value):
                return {"stored": "keyring", "key": key}
            _secrets_file_write(key, value)
            return {"stored": "file", "key": key}
        self._data[key] = value
        self._save()
        return {"stored": "config", "key": key}

    def delete_secret(self, key: str) -> bool:
        if key not in _SECRET_KEYS:
            return False
        kr_ok = _keyring_delete(key)
        sf_ok = _secrets_file_delete(key)
        return kr_ok or sf_ok

    def get_all(self) -> dict[str, str]:
        result: dict[str, str] = dict(self._data)
        for k in _SECRET_KEYS:
            val = self.get(k)
            if val and len(val) > 4:
                result[k] = "✓ set (" + "*" * 8 + val[-4:] + ")"
            elif val:
                result[k] = "✓ set"
            else:
                result[k] = "✗ not set"
        return result

    def reset(self) -> None:
        self._data = dict(DEFAULTS)
        self._save()

    def get_ignore_patterns(self) -> list[str]:
        raw = self.get("ignore_patterns", "")
        return [p.strip() for p in raw.split(",") if p.strip()]

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.get(key, default))
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        return str(self.get(key, str(default))).lower() in ("true", "1", "yes")

    @property
    def secret_keys(self) -> set[str]:
        return set(_SECRET_KEYS)
