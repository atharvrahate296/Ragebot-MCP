"""
Context Builder - Builds optimized context packs for different AI agent types.
Supports: debug | docs | refactor | review | test
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ragebot.storage.db import Database
    from ragebot.search.embedder import Embedder
    from ragebot.utils.tokens import TokenCounter


AGENT_PROMPTS = {
    "debug": (
        "You are a debugging assistant. Focus on error handling, exception paths, "
        "control flow, and potential failure points. Analyze the following project context."
    ),
    "docs": (
        "You are a documentation assistant. Focus on public APIs, function signatures, "
        "class hierarchies, and module purposes. Generate clear documentation."
    ),
    "refactor": (
        "You are a refactoring assistant. Focus on code smells, duplication, complexity, "
        "and opportunities for improvement. Suggest clean architecture patterns."
    ),
    "review": (
        "You are a code review assistant. Focus on correctness, security, performance, "
        "best practices, and potential bugs. Provide actionable feedback."
    ),
    "test": (
        "You are a testing assistant. Focus on identifying untested paths, edge cases, "
        "and generating comprehensive test cases for the following code."
    ),
}

AGENT_FOCUS_FIELDS = {
    "debug": ["functions", "classes", "imports", "error_handling"],
    "docs": ["functions", "classes", "imports", "summary", "docstrings"],
    "refactor": ["functions", "classes", "complexity"],
    "review": ["functions", "classes", "imports", "security"],
    "test": ["functions", "classes"],
}


class ContextBuilder:
    def __init__(self, db: "Database", embedder: "Embedder", token_counter: "TokenCounter"):
        self.db = db
        self.embedder = embedder
        self.token_counter = token_counter

    def build(
        self,
        agent_type: str,
        focus: Optional[str] = None,
        project_path: Optional[Path] = None,
    ) -> dict:
        """Build a targeted context pack."""
        agent_type = agent_type.lower()
        if agent_type not in AGENT_PROMPTS:
            agent_type = "review"

        # Get all files or focused subset
        if focus:
            files = [f for f in self.db.get_all_files()
                     if focus.lower() in f["file_path"].lower()]
        else:
            files = self.db.get_all_files()

        # Build context sections
        file_summaries = []
        code_sections = []
        total_tokens = 0

        for file_data in files[:50]:  # cap at 50 files
            meta = json.loads(file_data.get("metadata", "{}"))
            summary = file_data.get("summary", "")
            file_path = file_data["file_path"]

            file_context = {
                "file": file_path,
                "type": file_data.get("file_type", "unknown"),
                "summary": summary,
            }

            # Add agent-relevant fields
            for field in AGENT_FOCUS_FIELDS.get(agent_type, []):
                if field in meta:
                    file_context[field] = meta[field]

            file_summaries.append(file_context)

            # Get relevant chunks
            chunks = self.db.get_all_chunks()
            file_chunks = [c for c in chunks if c["file_path"] == file_path][:3]
            for chunk in file_chunks:
                token_count = self.token_counter.count(chunk["content"])
                total_tokens += token_count
                if total_tokens < 50000:  # ~50k token cap
                    code_sections.append({
                        "file": file_path,
                        "content": chunk["content"],
                        "tokens": token_count,
                    })

        return {
            "agent_type": agent_type,
            "system_prompt": AGENT_PROMPTS[agent_type],
            "project_path": str(project_path) if project_path else "",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "file_count": len(file_summaries),
            "token_count": total_tokens,
            "file_summaries": file_summaries,
            "code_sections": code_sections,
            "focus": focus,
            "instructions": (
                f"This context pack is optimized for {agent_type}. "
                f"It contains {len(file_summaries)} files and ~{total_tokens} tokens."
            ),
        }
