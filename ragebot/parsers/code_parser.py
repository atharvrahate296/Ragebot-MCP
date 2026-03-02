"""
Code Parser - Extracts structural information from source code files.
Supports Python (AST), and multiple languages via tree-sitter.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any


class CodeParser:
    def parse(self, content: str, extension: str, file_path: str = "") -> dict:
        """Parse source code and return structured metadata + chunks."""
        ext = extension.lower().lstrip(".")

        parsers = {
            "py": self._parse_python,
            "js": self._parse_generic,
            "ts": self._parse_generic,
            "jsx": self._parse_generic,
            "tsx": self._parse_generic,
            "java": self._parse_java_like,
            "cpp": self._parse_c_like,
            "c": self._parse_c_like,
            "h": self._parse_c_like,
            "go": self._parse_go,
            "rs": self._parse_rust,
            "rb": self._parse_generic,
            "php": self._parse_generic,
            "swift": self._parse_generic,
            "kt": self._parse_java_like,
            "cs": self._parse_java_like,
        }

        parser_fn = parsers.get(ext, self._parse_generic)
        result = parser_fn(content, file_path)
        result["type"] = "code"
        result["chunks"] = self._create_chunks(content, result)
        return result

    # ── Language Parsers ──────────────────────────────────────────────────────

    def _parse_python(self, content: str, file_path: str) -> dict:
        functions, classes, imports, docstrings = [], [], [], []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    functions.append(node.name)
                    if ast.get_docstring(node):
                        docstrings.append(f"{node.name}: {ast.get_docstring(node)[:100]}")
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                    if ast.get_docstring(node):
                        docstrings.append(f"{node.name}: {ast.get_docstring(node)[:100]}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

            # Module docstring
            module_doc = ast.get_docstring(tree) or ""
        except SyntaxError:
            module_doc = ""

        summary = self._build_summary(file_path, functions, classes, imports, module_doc)
        return {
            "functions": functions[:30],
            "classes": classes[:20],
            "imports": list(set(imports))[:20],
            "docstrings": docstrings[:10],
            "summary": summary,
        }

    def _parse_java_like(self, content: str, file_path: str) -> dict:
        functions = re.findall(r"(?:public|private|protected|static|void|[\w<>]+)\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+\w+\s*)?\{", content)
        classes = re.findall(r"(?:class|interface|enum)\s+(\w+)", content)
        imports = re.findall(r"import\s+(?:static\s+)?([\w.]+);", content)
        summary = self._build_summary(file_path, functions, classes, imports)
        return {
            "functions": list(set(functions))[:30],
            "classes": list(set(classes))[:20],
            "imports": list(set(imports))[:20],
            "summary": summary,
        }

    def _parse_c_like(self, content: str, file_path: str) -> dict:
        functions = re.findall(r"(?:[\w\*]+\s+)+(\w+)\s*\([^)]*\)\s*\{", content)
        includes = re.findall(r'#include\s*[<"]([^>"]+)[>"]', content)
        defines = re.findall(r"#define\s+(\w+)", content)
        summary = self._build_summary(file_path, functions, [], includes)
        return {
            "functions": list(set(functions))[:30],
            "classes": [],
            "imports": list(set(includes))[:20],
            "defines": defines[:20],
            "summary": summary,
        }

    def _parse_go(self, content: str, file_path: str) -> dict:
        functions = re.findall(r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(", content)
        structs = re.findall(r"type\s+(\w+)\s+struct", content)
        imports = re.findall(r'"([\w./]+)"', content)
        summary = self._build_summary(file_path, functions, structs, imports)
        return {
            "functions": list(set(functions))[:30],
            "classes": list(set(structs))[:20],
            "imports": list(set(imports))[:20],
            "summary": summary,
        }

    def _parse_rust(self, content: str, file_path: str) -> dict:
        functions = re.findall(r"(?:pub\s+)?fn\s+(\w+)\s*[<(]", content)
        structs = re.findall(r"(?:pub\s+)?(?:struct|enum|trait|impl)\s+(\w+)", content)
        imports = re.findall(r"use\s+([\w::{},\s]+);", content)
        summary = self._build_summary(file_path, functions, structs, imports)
        return {
            "functions": list(set(functions))[:30],
            "classes": list(set(structs))[:20],
            "imports": [i.strip() for i in imports][:20],
            "summary": summary,
        }

    def _parse_generic(self, content: str, file_path: str) -> dict:
        """Generic parser using regex patterns for JS/TS/Ruby/PHP etc."""
        # Functions: function foo(), const foo = () =>, def foo
        functions = re.findall(
            r"(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\(|def\s+(\w+))",
            content
        )
        functions = [next(f for f in match if f) for match in functions if any(match)]

        # Classes
        classes = re.findall(r"class\s+(\w+)", content)

        # Imports: import, require, from
        imports = re.findall(
            r"(?:import\s+.*?from\s+['\"]([^'\"]+)['\"]|require\s*\(\s*['\"]([^'\"]+)['\"]\))",
            content
        )
        imports = [next(i for i in match if i) for match in imports if any(match)]

        summary = self._build_summary(file_path, functions, classes, imports)
        return {
            "functions": list(set(functions))[:30],
            "classes": list(set(classes))[:20],
            "imports": list(set(imports))[:20],
            "summary": summary,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_summary(
        self,
        file_path: str,
        functions: list,
        classes: list,
        imports: list,
        docstring: str = "",
    ) -> str:
        parts = []
        if docstring:
            parts.append(docstring[:150])
        if classes:
            parts.append(f"Classes: {', '.join(classes[:5])}")
        if functions:
            parts.append(f"Functions: {', '.join(functions[:8])}")
        if imports:
            parts.append(f"Dependencies: {', '.join(imports[:5])}")
        return ". ".join(parts) if parts else f"Source file: {Path(file_path).name}"

    def _create_chunks(self, content: str, parsed: dict, chunk_size: int = 512) -> list[str]:
        """Split code into meaningful chunks."""
        lines = content.split("\n")
        chunks = []
        current_chunk: list[str] = []
        current_size = 0

        for line in lines:
            line_len = len(line.split())
            if current_size + line_len > chunk_size and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_size = line_len
            else:
                current_chunk.append(line)
                current_size += line_len

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks if chunks else [content[:2000]]
