"""Resolve a tree-sitter grammar from a file extension.

Grammar selection is by extension via tree-sitter-language-pack. An unknown
extension (or a grammar the pack cannot load) yields no parser, and the caller
falls through to the synthetic delimiter cascade. Loaded parsers are cached
because building one is not free.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from tree_sitter import Parser
from tree_sitter_language_pack import get_parser

_LANG_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".java": "java",
    ".kt": "kotlin",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".rb": "ruby",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".sh": "bash",
    ".sql": "sql",
    ".gradle": "groovy",
    ".groovy": "groovy",
    ".md": "markdown",
    ".mdx": "markdown",
    ".html": "html",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
}


def parser_for(path: Path) -> Parser | None:
    """Return a parser for ``path``'s extension, or None when there is none."""
    lang = _LANG_BY_EXT.get(path.suffix.lower())
    return _load(lang) if lang is not None else None


@cache
def _load(lang: str) -> Parser | None:
    try:
        return get_parser(lang)  # type: ignore[arg-type]
    except Exception:
        return None
