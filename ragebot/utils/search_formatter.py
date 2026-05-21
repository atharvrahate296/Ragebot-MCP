# ragebot/utils/search_formatter.py
"""
Search Formatter - Enhanced search results with file paths, line numbers, and snippets.
Provides structured, readable search output with proper context display.
"""
from __future__ import annotations

from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax


class SearchResultFormatter:
    """Format and display search results with rich context."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def format_results(
        self,
        results: list[dict],
        query: str = "",
        max_preview_length: int = 150,
    ) -> None:
        """
        Display search results with richer result cards, score bars, and per-result panels.

        Args:
            results: List of search result dicts with file_path, score, content, etc.
            query: The original search query (for context)
            max_preview_length: Max chars in preview snippet
        """
        if not results:
            self.console.print(
                Panel("[yellow]No results found.[/yellow]",
                      border_style="yellow", expand=False)
            )
            return

        if query:
            self.console.print(
                Panel(f"[bold cyan]🔍 {query}[/bold cyan]  "
                      f"[dim]→ {len(results)} result(s)[/dim]",
                      border_style="cyan", padding=(0, 2), expand=False)
            )

        for i, r in enumerate(results[:20], 1):
            file_path = r.get("file_path") or r.get("file", "?")
            score     = r.get("score", 0)
            ftype     = r.get("file_type", r.get("type", ""))
            content   = r.get("content", r.get("preview", ""))

            # Score bar (0–1 → 10 chars)
            bar_len  = max(1, int(score * 10)) if isinstance(score, float) else 0
            bar      = "█" * bar_len + "░" * (10 - bar_len)
            score_str = f"[green]{bar}[/green] {score:.3f}" if isinstance(score, float) else str(score)

            preview = self._create_preview(content, max_preview_length)

            self.console.print(
                Panel(
                    f"[dim]{score_str}[/dim]\n{preview}",
                    title=f"[bold cyan]{i}.[/bold cyan] [yellow]{file_path}[/yellow]  [dim]{ftype}[/dim]",
                    border_style="blue",
                    padding=(0, 2),
                    expand=False,
                )
            )


    
    def format_result_detailed(
        self,
        result: dict,
        show_code_syntax: bool = True,
    ) -> None:
        """
        Display a single search result with full content.
        
        Args:
            result: Search result dict
            show_code_syntax: Whether to highlight code with syntax coloring
        """
        self._display_detailed_result(result, show_code_syntax=show_code_syntax)
    
    def _display_detailed_result(
        self,
        result: dict,
        title: str = "[bold]Result[/bold]",
        show_code_syntax: bool = True,
    ) -> None:
        """Display detailed view of a single result."""
        file_path = result.get("file_path") or result.get("file", "unknown")
        file_type = result.get("file_type", "unknown")
        content = result.get("content", "")
        score = result.get("score", 0)
        
        # File info panel
        info_lines = [
            f"[cyan]File:[/cyan] {file_path}",
            f"[cyan]Type:[/cyan] {file_type}",
            f"[cyan]Score:[/cyan] {score:.3f}" if isinstance(score, float) else f"[cyan]Score:[/cyan] {score}",
            f"[cyan]Content Length:[/cyan] {len(content)} chars",
        ]
        
        self.console.print(Panel(
            "\n".join(info_lines),
            title=title,
            border_style="green",
            padding=(0, 2),
        ))
        
        # Content panel with optional syntax highlighting
        if content:
            self.console.print()
            
            # Determine language for syntax highlighting
            if show_code_syntax:
                lang = self._detect_language(file_path, file_type)
            else:
                lang = "text"
            
            # Show content with syntax highlighting if available
            try:
                if lang != "text" and show_code_syntax:
                    syntax_obj = Syntax(
                        content[:2000],  # Limit to 2000 chars for display
                        lang,
                        theme="monokai",
                        line_numbers=True,
                    )
                    self.console.print(Panel(
                        syntax_obj,
                        title="[cyan]Content Preview[/cyan]",
                        border_style="blue",
                        padding=(0, 1),
                    ))
                else:
                    # Plain text display
                    preview = content[:1000]
                    if len(content) > 1000:
                        preview += "\n\n[dim]... (truncated)[/dim]"
                    self.console.print(Panel(
                        preview,
                        title="[cyan]Content Preview[/cyan]",
                        border_style="blue",
                        padding=(0, 1),
                    ))
            except Exception:
                # Fallback to plain display on syntax error
                preview = content[:1000]
                self.console.print(Panel(
                    preview,
                    title="[cyan]Content Preview[/cyan]",
                    border_style="blue",
                    padding=(0, 1),
                ))
    
    def _create_preview(self, content: str, max_length: int = 150) -> str:
        """
        Create a short preview from content.
        Takes first non-empty line or first N characters.
        """
        if not content:
            return "[dim](empty)[/dim]"
        
        # Try to get first meaningful line
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                if len(line) > max_length:
                    return line[:max_length] + "..."
                return line
        
        # Fallback to first N chars
        preview = content[:max_length].replace("\n", " ")
        if len(content) > max_length:
            preview += "..."
        return preview
    
    def _shorten_path(self, path: str, max_length: int = 30) -> str:
        """
        Shorten file path for display.
        Shows filename + parent directory if it fits.
        """
        if len(path) <= max_length:
            return path
        
        # Try to show: ...parent/filename
        parts = path.replace("\\", "/").split("/")
        if len(parts) >= 2:
            return "..." + "/".join(parts[-2:])
        
        # Fallback: truncate with ellipsis
        return path[:max_length-3] + "..."
    
    def _detect_language(self, file_path: str, file_type: str) -> str:
        """Detect language for syntax highlighting."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "jsx",
            ".tsx": "tsx",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".cs": "csharp",
            ".sql": "sql",
            ".sh": "bash",
            ".html": "html",
            ".xml": "xml",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".md": "markdown",
        }
        
        # Check by file extension
        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        
        # Check by file_type
        if file_type == "code":
            return "python"  # Default code language
        
        return "text"
    
    def format_search_summary(self, results: list[dict], total_count: int = 0) -> None:
        """Display summary of search results."""
        if not results:
            self.console.print("[yellow]No results found.[/yellow]")
            return
        
        # Stats
        avg_score = sum(r.get("score", 0) for r in results) / len(results) if results else 0
        file_types = {}
        for r in results:
            ft = r.get("file_type", "unknown")
            file_types[ft] = file_types.get(ft, 0) + 1
        
        self.console.print(Panel(
            f"[cyan]Total Results:[/cyan] {total_count or len(results)}\n"
            f"[cyan]Average Score:[/cyan] {avg_score:.3f}\n"
            f"[cyan]File Types:[/cyan] {', '.join(f'{k}({v})' for k, v in file_types.items())}",
            title="[bold]Search Summary[/bold]",
            border_style="cyan",
            padding=(0, 2)
        ))


class DocFormatter:
    """Format generated documentation."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def format_generated_docs(
        self,
        file_path: str,
        content: str,
        title: str = "📖 Generated Documentation",
    ) -> None:
        """
        Display generated documentation in a structured format.
        """
        from rich.markdown import Markdown
        
        # Header
        self.console.print(Panel(
            f"[bold cyan]{title}[/bold cyan]\n[dim]{file_path}[/dim]",
            border_style="cyan",
            padding=(1, 2)
        ))
        
        # Render as markdown
        try:
            md = Markdown(content)
            self.console.print(md)
        except Exception:
            # Fallback to plain text
            self.console.print(content)
    
    def format_readme_style_docs(
        self,
        title: str,
        summary: str,
        sections: dict[str, str],
    ) -> str:
        """
        Generate README-style documentation structure.
        Returns markdown string.
        """
        lines = [
            f"# {title}",
            "",
            summary,
            "",
        ]
        
        for section_title, section_content in sections.items():
            lines.append(f"## {section_title}")
            lines.append("")
            lines.append(section_content)
            lines.append("")
        
        return "\n".join(lines)
