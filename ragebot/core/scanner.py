"""
Directory Scanner - Recursively scans and classifies project files.
"""
from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Generator, List

from ragebot.core.config import ConfigManager


# File type classification
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".c", ".h",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".cs",
    ".r", ".m", ".lua", ".sh", ".bash", ".zsh", ".fish",
}
DOC_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".rst", ".tex"}
CONFIG_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
    ".xml", ".properties",
}
ASSET_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".mp4",
    ".mp3", ".wav", ".ttf", ".woff", ".woff2",
}


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
        ext = path.suffix.lower()
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
        name = path.name
        rel = str(path.relative_to(self.root))

        for pattern in self._ignore_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
            if fnmatch.fnmatch(rel, pattern):
                return True
            # Exact directory name match
            if path.is_dir() and name == pattern:
                return True

        # Hidden files/dirs (except .env)
        if name.startswith(".") and name not in (".env", ".gitignore"):
            return True

        return False

    def _is_indexable(self, path: Path) -> bool:
        ext = path.suffix.lower()
        # Skip assets
        if ext in ASSET_EXTENSIONS:
            return False
        # Skip files that are too large
        try:
            size_kb = path.stat().st_size / 1024
            if size_kb > self._max_size_kb:
                return False
        except OSError:
            return False
        return True

    def _build_tree(self, directory: Path, lines: list, prefix: str, depth: int):
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
