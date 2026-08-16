"""Baked splitting budgets, the delimiter cascade, and section categories.

Operating constants from the settled recipe, not config: the passage budget and
the tiny/group thresholds, the ordered delimiter cascade, and the extension ->
category -> section-budget table (code and docs 10 KB, data 2 KB — each a
log-scale Kneedle knee of file-size distributions measured over four large
repos). Values live here as data so the packer walks a table, not literals.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PASSAGE_BYTES = 800
MIN_PARA = 64
MIN_GROUP = 100


@dataclass(frozen=True)
class Delimiter:
    """One cascade level: a display name and the bytes it splits on."""

    name: str
    separator: bytes


CASCADE: tuple[Delimiter, ...] = (
    Delimiter("blank-line", b"\n\n"),
    Delimiter("line", b"\n"),
    Delimiter("sentence", b". "),
    Delimiter("comma", b","),
    Delimiter("word", b" "),
)

_SECTION_BYTES: dict[str, int] = {"code": 10240, "docs": 10240, "data": 2048}
_DEFAULT_CATEGORY = "docs"
_CATEGORY_BY_EXT: dict[str, str] = {
    ".py": "code",
    ".java": "code",
    ".kt": "code",
    ".js": "code",
    ".jsx": "code",
    ".ts": "code",
    ".tsx": "code",
    ".go": "code",
    ".rb": "code",
    ".rs": "code",
    ".c": "code",
    ".h": "code",
    ".cpp": "code",
    ".hpp": "code",
    ".cs": "code",
    ".php": "code",
    ".sh": "code",
    ".sql": "code",
    ".md": "docs",
    ".mdx": "docs",
    ".rst": "docs",
    ".txt": "docs",
    ".html": "docs",
    ".json": "data",
    ".yaml": "data",
    ".yml": "data",
    ".toml": "data",
    ".xml": "data",
    ".csv": "data",
    ".ini": "data",
    ".cfg": "data",
}


def section_budget(path: Path) -> int:
    """Return the section byte budget for a file, by its extension category."""
    category = _CATEGORY_BY_EXT.get(path.suffix.lower(), _DEFAULT_CATEGORY)
    return _SECTION_BYTES[category]
