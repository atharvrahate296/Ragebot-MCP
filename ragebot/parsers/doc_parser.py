"""
Document Parser - Extracts and chunks content from PDF, DOCX, MD, and TXT files.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class DocumentParser:
    def parse(self, file_path: Path) -> dict:
        """Parse a document file and return structured content."""
        ext = file_path.suffix.lower()
        parsers = {
            ".pdf": self._parse_pdf,
            ".docx": self._parse_docx,
            ".md": self._parse_markdown,
            ".txt": self._parse_text,
            ".rst": self._parse_text,
            ".tex": self._parse_text,
        }
        parser_fn = parsers.get(ext, self._parse_text)
        return parser_fn(file_path)

    # ── Parsers ───────────────────────────────────────────────────────────────

    def _parse_pdf(self, path: Path) -> dict:
        text = ""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(path))
            pages = []
            for page in doc:
                pages.append(page.get_text())
            text = "\n".join(pages)
            doc.close()
        except ImportError:
            try:
                import pdfplumber
                with pdfplumber.open(str(path)) as pdf:
                    text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            except ImportError:
                text = f"[PDF parsing unavailable. Install PyMuPDF: pip install pymupdf]"
        except Exception as e:
            text = f"[PDF parsing error: {e}]"

        return self._build_result(text, "pdf", str(path))

    def _parse_docx(self, path: Path) -> dict:
        text = ""
        try:
            from docx import Document
            doc = Document(str(path))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            # Also extract tables
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            paragraphs.append(cell.text)
            text = "\n".join(paragraphs)
        except ImportError:
            text = "[DOCX parsing unavailable. Install python-docx: pip install python-docx]"
        except Exception as e:
            text = f"[DOCX parsing error: {e}]"

        return self._build_result(text, "docx", str(path))

    def _parse_markdown(self, path: Path) -> dict:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return self._build_result("", "markdown", str(path))

        # Extract headings for structure
        headings = re.findall(r"^#{1,6}\s+(.+)$", text, re.MULTILINE)

        # Strip markdown syntax for clean text
        clean = re.sub(r"```[\s\S]*?```", "[code block]", text)
        clean = re.sub(r"`[^`]+`", lambda m: m.group()[1:-1], clean)
        clean = re.sub(r"!\[.*?\]\(.*?\)", "[image]", clean)
        clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", clean)
        clean = re.sub(r"#{1,6}\s+", "", clean)
        clean = re.sub(r"\*\*(.+?)\*\*", r"\1", clean)
        clean = re.sub(r"\*(.+?)\*", r"\1", clean)

        result = self._build_result(clean, "markdown", str(path))
        result["headings"] = headings
        return result

    def _parse_text(self, path: Path) -> dict:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = ""
        return self._build_result(text, "text", str(path))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_result(self, text: str, doc_type: str, file_path: str) -> dict:
        text = text.strip()
        summary = self._extract_summary(text)
        chunks = self._chunk_text(text)
        return {
            "type": doc_type,
            "summary": summary,
            "chunks": chunks,
            "char_count": len(text),
            "chunk_count": len(chunks),
        }

    def _extract_summary(self, text: str, max_chars: int = 300) -> str:
        """Extract the first meaningful paragraph as a summary."""
        if not text:
            return ""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for para in paragraphs:
            if len(para) > 50:
                return para[:max_chars]
        return text[:max_chars]

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        """Split text into overlapping chunks."""
        if not text:
            return []
        words = text.split()
        if not words:
            return []

        chunks = []
        start = 0
        while start < len(words):
            end = start + chunk_size
            chunk_words = words[start:end]
            chunks.append(" ".join(chunk_words))
            if end >= len(words):
                break
            start = end - overlap  # overlap

        return chunks if chunks else [text[:2000]]
