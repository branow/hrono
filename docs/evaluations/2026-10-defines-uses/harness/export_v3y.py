"""The v3 export with one sub-tree rebuilt: the 21 slice leaf topics get the
B briefs (written with linked condensations), their 6 upper topics get the
rebuilt upper briefs (arm C), and each of the 21 leaf topics gets
condensations.md: the ledger condensation of every section in it, so the
lists and conditions a brief drops are in the export too.

Usage: uv run python export_v3y.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

import exp
from exp import c

SRC = Path.home() / "hrono-eval" / "export-bcreg-v3-L3"
DST = Path.home() / "hrono-eval" / "export-bcreg-v3y-L3"


def folder(node: int) -> Path:
    hits = [p for p in DST.rglob(f"*-{node}") if p.is_dir()]
    assert len(hits) == 1, (node, hits)
    return hits[0]


def swap(path: Path, text: str, marker: str) -> None:
    """The brief part of an exported file replaced; the listing the
    exporter renders below `marker` kept."""
    old = path.read_text()
    i = old.index(marker)
    path.write_text(text.strip() + "\n\n" + old[i:])


def main() -> None:
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)
    conn = c.connect()
    leaves = {int(k): v["text"] for k, v in exp.load("briefs-B.json").items()}
    uppers = {int(k): v["text"] for k, v in exp.load("upper-C.json").items()}
    ledger = exp.load("ledger.json")
    for node, text in leaves.items():
        d = folder(node)
        rows = conn.execute(
            "SELECT s.id, s.source, s.path FROM node_members m "
            "JOIN sections s ON s.id = m.section_id WHERE m.node_id = ? "
            "ORDER BY s.source, s.path, s.ordinal",
            (node,),
        ).fetchall()
        blocks = [
            f"## {source}/{path}\n\n"
            + (
                ledger[str(sid)]["text"]
                if str(sid) in ledger
                else exp.stored_condensation(conn, sid)
            )
            for sid, source, path in rows
        ]
        (d / "condensations.md").write_text(
            "# Condensations of this topic's sections\n\n"
            "One condensation per section, under its file: the exact checks, "
            "lists, error handling and calls the brief leaves out.\n\n"
            + "\n\n".join(blocks)
            + "\n"
        )
        swap(
            d / "brief.md",
            text
            + "\n\nCondensation of every section of this topic: "
            "[condensations.md](condensations.md).",
            "## Sources",
        )
    for node, text in uppers.items():
        swap(folder(node) / "brief.md", text, "## Children")
    print("leaves", len(leaves), "uppers", len(uppers), "->", DST)


if __name__ == "__main__":
    main()
