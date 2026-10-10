"""The export built on request and kept, so showing it never builds it.

``produce`` renders every file in a tree. The Export page used to call it on
every view, which on a 9,000-section tree is about ten seconds per click. Now
the ``export`` op builds one when someone presses Export and stores it here,
and the page and its download read the stored copy.

The stored copy is the archive ``produce`` would hand out, plus what the page
shows beside it: the shape, the counts and the topics without a usable brief.
"""

from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from hrono.export.collapse import Shape
from hrono.export.produce import Export, archive, produce
from hrono.naming import name
from hrono.summarize import briefs

ROOT_PAGE = "root.md"


@dataclass(frozen=True)
class Flag:
    """An exported topic whose brief is missing or was stored flagged."""

    title: str
    why: str
    page: str


@dataclass(frozen=True)
class Saved:
    """One tree's kept export: its archive and what the page says about it."""

    tree: str
    levels: int
    built_at: str
    shape: Shape
    files: int
    size: int
    flagged: tuple[Flag, ...]
    archive: bytes

    def pages(self) -> frozenset[str]:
        with zipfile.ZipFile(io.BytesIO(self.archive)) as bundle:
            return frozenset(bundle.namelist())

    def read(self, page: str) -> str | None:
        """One file of the export, or None when the export has no such file."""
        with zipfile.ZipFile(io.BytesIO(self.archive)) as bundle:
            try:
                return bundle.read(page).decode("utf-8")
            except KeyError:
                return None


def build(conn: sqlite3.Connection, tree: str, levels: int) -> Saved | None:
    """Produce the export at ``levels`` hops; None when the tree is unbuilt."""
    made = produce(conn, tree, levels)
    if made is None:
        return None
    return Saved(
        tree=tree,
        levels=levels,
        built_at=datetime.now(UTC).isoformat(timespec="seconds"),
        shape=made.shape,
        files=len(made.files),
        size=sum(len(text.encode("utf-8")) for text in made.files.values()),
        flagged=tuple(_flagged(conn, made)),
        archive=archive(made.files),
    )


def save(conn: sqlite3.Connection, saved: Saved) -> None:
    """Keep ``saved`` as its tree's export, replacing the one before."""
    meta = {
        "shape": asdict(saved.shape),
        "files": saved.files,
        "size": saved.size,
        "flagged": [asdict(flag) for flag in saved.flagged],
    }
    conn.execute(
        "INSERT OR REPLACE INTO exports (tree, levels, built_at, meta, archive)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            saved.tree,
            saved.levels,
            saved.built_at,
            json.dumps(meta),
            saved.archive,
        ),
    )


def load(conn: sqlite3.Connection, tree: str) -> Saved | None:
    """The tree's kept export, or None when nobody has exported it yet."""
    row = conn.execute(
        "SELECT levels, built_at, meta, archive FROM exports WHERE tree = ?",
        (tree,),
    ).fetchone()
    if row is None:
        return None
    meta = json.loads(row["meta"])
    shown = meta["shape"]
    return Saved(
        tree=tree,
        levels=int(row["levels"]),
        built_at=str(row["built_at"]),
        shape=Shape(
            **{**shown, "pages_per_level": tuple(shown["pages_per_level"])}
        ),
        files=int(meta["files"]),
        size=int(meta["size"]),
        flagged=tuple(Flag(**flag) for flag in meta["flagged"]),
        archive=bytes(row["archive"]),
    )


def _flagged(conn: sqlite3.Connection, made: Export) -> list[Flag]:
    """Exported topics whose brief is missing or was stored flagged."""
    ids = sorted(made.tree.nodes)
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        "SELECT n.id AS id, b.flagged AS flagged, b.text AS text, "  # noqa: S608
        f"b.node_id AS has, {briefs.TEMPLATE} AS template "
        f"FROM nodes n LEFT JOIN briefs b ON b.node_id = n.id "
        f"WHERE n.id IN ({marks}) ORDER BY n.id",
        ids,
    ).fetchall()
    out: list[Flag] = []
    for row in rows:
        why = "no brief" if row["has"] is None else _refusal(conn, row)
        if why:
            node_id = int(row["id"])
            out.append(Flag(name(conn, node_id), why, _page_of(made, node_id)))
    return out


def _refusal(conn: sqlite3.Connection, row: sqlite3.Row) -> str:
    return briefs.refusal(
        conn, int(row["id"]), row["flagged"], row["text"], row["template"]
    )


def _page_of(made: Export, node_id: int) -> str:
    if node_id == made.tree.root:
        return ROOT_PAGE
    suffix = f"-{node_id}/brief.md"
    return next(
        (p for p in sorted(made.files) if p.endswith(suffix)), ROOT_PAGE
    )
