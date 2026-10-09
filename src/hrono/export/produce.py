"""One export, produced once for every door that hands it out.

The JSON manifest the CLI writes to a folder, the archive the panel downloads
and the pages the panel shows are the same files; producing them in one place is
what makes "the archive unpacks to what `hrono tree export` writes" true by
construction rather than by two code paths happening to agree.
"""

from __future__ import annotations

import io
import sqlite3
import zipfile
from dataclasses import dataclass

from hrono import notes
from hrono.export import store
from hrono.export.collapse import ExportTree, Shape, collapse, shape
from hrono.export.render import render

# A zip entry stamps a date; a fixed one keeps the same export the same bytes.
_EPOCH = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class Export:
    """The rendered files, keyed by relative path, and the shape they make."""

    files: dict[str, str]
    shape: Shape
    tree: ExportTree


def produce(conn: sqlite3.Connection, name: str, levels: int) -> Export | None:
    """Render tree ``name`` at hop limit ``levels``; None when it is unbuilt."""
    stored = store.load(conn, name)
    if stored is None:
        return None
    agent_tree = collapse(stored, levels)
    files = render(conn, agent_tree, notes=notes.rendered(conn, notes.NODE))
    return Export(files=files, shape=shape(agent_tree), tree=agent_tree)


def archive(files: dict[str, str]) -> bytes:
    """The files as one zip, entries in path order, the same bytes each time."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(files):
            entry = zipfile.ZipInfo(path, date_time=_EPOCH)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            bundle.writestr(entry, files[path].encode("utf-8"))
    return buffer.getvalue()
