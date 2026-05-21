# ragebot/core/scanner.py
"""
Directory Scanner - Recursively scans and classifies project files.
Enhanced with expanded file type support and improved ignore handling.
"""
from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Generator, List

from ragebot.core.config import ConfigManager


# ── Always-ignored directories (CRITICAL: never indexed, never traversed) ───
ALWAYS_IGNORE_DIRS: set[str] = {
    # Python virtual environments & packaging
    "env", "venv", ".venv", ".env", "ENV", "Env",
    ".conda", "conda-env", "__pycache__", ".eggs",
    "dist", "build", "*.egg-info", ".eggs",
    # Node.js ecosystem
    "node_modules", ".npm", "bower_components", "pnpm-store",
    # Ruby/Python package managers
    ".bundle", "Gemfile.lock", "vendor",
    # Version control
    ".git", ".hg", ".svn", ".gitattributes",
    # IDE / editor
    ".vscode", ".idea", ".vs", ".vim", ".emacs.d",
    ".sublime-project", ".sublime-workspace",
    # RageBot's own data
    ".ragebot",
    # OS junk & system files
    ".DS_Store", "Thumbs.db", ".AppleDouble", ".LSOverride",
    "desktop.ini", "$RECYCLE.BIN", "thumbs.db",
    # Test/lint caches
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".flake8_cache",
    ".tox", ".nox", "htmlcov", ".coverage",
    # CI/CD
    ".github", ".gitlab-ci", ".circleci", ".travis.yml", "appveyor.yml",
    # Build artifacts & dependencies
    ".gradle", ".m2", "target", "build", "dist", "out",
    ".cargo", "Cargo.lock", "node_modules", ".next", ".nuxt",
    # Docker & container stuff
    ".dockerignore", ".docker",
    # Lock files (generally large, auto-generated)
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Pipfile.lock",
    "Gemfile.lock", "composer.lock", "poetry.lock",
    # Database & cache files
    ".sqlite", ".db", "*.sqlite3", ".cache", "tmp", "temp",
    # Documentation builds
    "_build", "_site", "site", "docs/_build", ".jekyll-cache",
    # Logs
    "logs", "log", "*.log",
}

# ── Expanded file type classification ────────────────────────────────────────
CODE_EXTENSIONS = {
    # Python
    ".py", ".pyx", ".pyi", ".pxd",
    # JavaScript/TypeScript
    ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
    # Java/JVM
    ".java", ".kt", ".scala", ".clj", ".groovy",
    # C/C++/C#
    ".cpp", ".c", ".h", ".hpp", ".cc", ".cxx", ".hh", ".cs",
    # Go
    ".go",
    # Rust
    ".rs",
    # Ruby
    ".rb", ".rake",
    # PHP
    ".php", ".phtml", ".php3", ".php4", ".php5",
    # Swift/Objective-C
    ".swift", ".m", ".mm",
    # Shell
    ".sh", ".bash", ".zsh", ".fish",
    # Other compiled languages
    ".r", ".R", ".lua", ".pl", ".pm", ".ex", ".exs", ".erl", ".hrl",
    # SQL
    ".sql", ".plsql",
    # JSON/YAML/TOML (often code)
    ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    # XML/HTML-like
    ".xml", ".html", ".htm", ".xhtml", ".vue", ".svelte",
    # Dockerfile & config
    ".Dockerfile", "Dockerfile",
    # Makefiles
    "Makefile", "makefile",
}

DOC_EXTENSIONS = {
    # Markdown variants
    ".md", ".markdown", ".mdown", ".mkd", ".mkdn",
    # ReStructuredText
    ".rst", ".rest",
    # Markup
    ".tex", ".latex",
    # Documents
    ".pdf", ".docx", ".doc", ".odt", ".rtf",
    # Plain text
    ".txt",
    # Man pages
    ".man", ".1", ".2",
    # AsciiDoc
    ".asciidoc", ".adoc",
}

CONFIG_EXTENSIONS = {
    ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".conf", ".config", ".env", ".env.example", ".env.sample",
    ".xml", ".properties", ".gradle", ".cmake",
}

ASSET_EXTENSIONS = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp",
    # Audio/Video
    ".mp3", ".mp4", ".wav", ".flac", ".m4a", ".aac", ".webm", ".mkv",
    # Fonts
    ".ttf", ".woff", ".woff2", ".otf", ".eot",
    # Archives
    ".zip", ".tar", ".gz", ".rar", ".7z", ".bz2",
    # Compiled
    ".so", ".dll", ".dylib", ".exe", ".o", ".a",
}

# Cache/build artifacts to exclude
CACHE_ARTIFACT_PATTERNS = {
    "*.pyc", "*.pyo", "*.pyd", "*.so",
    "*.o", "*.a", "*.lib", "*.dll", "*.exe",
    "*.egg-info", "*.dist-info",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "__pycache__", ".tox", ".nox",
    "node_modules", "dist", "build", "target",
    ".gradle", ".m2",
}


def _looks_like_virtualenv(path: Path) -> bool:
    """Heuristic: detect virtualenv directories by marker files."""
    if not path.is_dir():
        return False
    # Standard virtualenv / venv marker
    if (path / "pyvenv.cfg").exists():
        return True
    # Windows virtualenv layout
    if (path / "Lib" / "site-packages").is_dir():
        return True
    # Unix virtualenv layout
    if (path / "lib").is_dir() and (path / "bin" / "activate").exists():
        return True
    # Poetry/pipenv
    if (path / ".venv").is_dir():
        return True
    return False


def _looks_like_node_modules(path: Path) -> bool:
    """Detect node_modules or package management cache."""
    name = path.name.lower()
    return name in ("node_modules", ".npm", "pnpm-store", "bower_components")


class DirectoryScanner:
    def __init__(self, root: Path, config: ConfigManager):
        self.root = root
        self.config = config
        self._ignore_patterns = config.get_ignore_patterns()
        self._max_size_kb = config.get_int("max_file_size_kb", 500)
        self._max_depth = config.get_int("index_depth", 10)

    def scan(self) -> List[Path]:
        """Return list of all indexable files under root."""
        files = []
        for path in self._walk():
            if self._is_indexable(path):
                files.append(path)
        return files

    def get_tree_string(self) -> str:
        """Return a tree-style string representation of the project."""
        lines = [str(self.root.name) + "/"]
        self._build_tree(self.root, lines, prefix="", depth=0)
        return "\n".join(lines)

    def classify(self, path: Path) -> str:
        """Classify a file by type: code, doc, config, asset, or other."""
        ext = path.suffix.lower()
        name = path.name.lower()
        
        # Check by name first (Dockerfile, Makefile, etc.)
        if name in ("Dockerfile", "dockerfile", "Makefile", "makefile"):
            return "code"
        
        if ext in CODE_EXTENSIONS:
            return "code"
        if ext in DOC_EXTENSIONS:
            return "doc"
        if ext in CONFIG_EXTENSIONS:
            return "config"
        if ext in ASSET_EXTENSIONS:
            return "asset"
        return "other"

    # ── Private ───────────────────────────────────────────────────────────────

    def _walk(self) -> Generator[Path, None, None]:
        """Walk directory tree respecting ignore patterns and depth."""
        yield from self._walk_dir(self.root, depth=0)

    def _walk_dir(self, directory: Path, depth: int) -> Generator[Path, None, None]:
        if depth > self._max_depth:
            return
        try:
            entries = sorted(directory.iterdir())
        except PermissionError:
            return

        for entry in entries:
            if self._should_ignore(entry):
                continue
            if entry.is_dir():
                yield from self._walk_dir(entry, depth + 1)
            elif entry.is_file():
                yield entry

    def _should_ignore(self, path: Path) -> bool:
        """Determine if a path should be skipped during scanning."""
        name = path.name
        
        # ── 1. Always-ignore list (fast, unconditional) ───────────────────
        if name in ALWAYS_IGNORE_DIRS:
            return True
        
        # ── 2. Heuristic virtualenv/node_modules detection ─────────────────
        if path.is_dir():
            if _looks_like_virtualenv(path) or _looks_like_node_modules(path):
                return True
        
        # ── 3. Config-based ignore patterns (glob-style) ──────────────────
        rel = str(path.relative_to(self.root))
        for pattern in self._ignore_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
            if fnmatch.fnmatch(rel, pattern):
                return True
            if fnmatch.fnmatch(rel.replace("\\", "/"), pattern):
                return True
            if path.is_dir() and name == pattern:
                return True
        
        # ── 4. Cache artifact patterns ─────────────────────────────────────
        for artifact_pattern in CACHE_ARTIFACT_PATTERNS:
            if fnmatch.fnmatch(name, artifact_pattern):
                return True
        
        # ── 5. Hidden files/dirs (except known safe ones) ─────────────────
        if name.startswith(".") and name not in (".gitignore", ".env.example", ".env.sample"):
            return True
        
        # ── 6. Backup files ────────────────────────────────────────────────
        if name.endswith(("~", ".bak", ".swp", ".swo", ".tmp")):
            return True

        return False

    def _is_indexable(self, path: Path) -> bool:
        """Determine if a file should be indexed."""
        ext = path.suffix.lower()
        
        # Skip assets entirely
        if ext in ASSET_EXTENSIONS:
            return False
        
        # Skip lock files (large, auto-generated)
        if path.name in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml",
                         "Pipfile.lock", "poetry.lock", "Gemfile.lock", "composer.lock"):
            return False
        
        # Skip compiled binaries
        if ext in (".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".o"):
            return False
        
        # Check file size
        try:
            size_kb = path.stat().st_size / 1024
            if size_kb > self._max_size_kb:
                return False
        except OSError:
            return False
        
        return True

    def _build_tree(self, directory: Path, lines: list, prefix: str, depth: int):
        """Build tree representation recursively."""
        if depth > 4:  # tree display limit
            return
        try:
            entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return

        entries = [e for e in entries if not self._should_ignore(e)]
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                extension = "    " if is_last else "│   "
                self._build_tree(entry, lines, prefix + extension, depth + 1)
