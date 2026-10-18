# ruff: noqa: E501, SIM115 - experiment harness
"""Round 9, step 4: the two questions' sub-tree rebuilt by hrono's own code.

A copy of the v3 tree (`hrono-v9.db`) with the new seeded prompts and the
tree's "Look into other topics" setting on. Only the sub-tree is rebuilt, so
the run costs dollars rather than a whole build:
1. the condensations of the 16 leaf topics' sections are deleted, and hrono's
   `condense` op writes them again with the new prompt (every other section
   keeps its stored condensation, which is what lookups read elsewhere);
2. hrono's `brief` op rewrites those 16 leaf briefs, with lookups;
3. hrono's `brief-upper` op rewrites each of their ancestors, lowest first;
4. the export is written by hrono's export renderer.

Usage: uv run --extra claude-code --extra cluster python subtree_v9.py build
       uv run --extra claude-code python subtree_v9.py leaves
       uv run python subtree_v9.py export
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import exp
import investigate

sys.path.insert(0, str(exp.HERE.parents[3] / "src"))
from hrono.cluster import repair  # noqa: E402
from hrono.db.database import Database  # noqa: E402
from hrono.export import saved  # noqa: E402
from hrono.jobs.model import Job  # noqa: E402
from hrono.jobs.ops import JobContext  # noqa: E402
from hrono.registry import store  # noqa: E402
from hrono.registry.collections.prompts import _DEFAULTS  # noqa: E402
from hrono.registry.write import content_hash  # noqa: E402
from hrono.summarize.brief import brief  # noqa: E402
from hrono.summarize.brief_upper import brief_upper  # noqa: E402
from hrono.summarize.condense import condense  # noqa: E402

SRC = Path.home() / "hrono-eval" / "db" / "hrono-v3.db"
DST = Path.home() / "hrono-eval" / "db" / "hrono-v9.db"
CACHE = Path.home() / "hrono-eval" / "v9-cache"
TREE = "bcreg"


def _job(op: str, scope: dict[str, object]) -> Job:
    return Job(
        id=f"v9-{op}",
        parent_id=None,
        tree=TREE,
        op=op,
        scope=scope,
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


def copy() -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(str(DST) + suffix).unlink(missing_ok=True)
    with sqlite3.connect(f"file:{SRC}?mode=ro", uri=True) as src:
        dst = sqlite3.connect(DST)
        src.backup(dst)
        dst.close()


def build() -> None:
    copy()
    database = Database.at(DST)  # migrates: brief_uses appears
    leaves = investigate.question_leaves(exp.c.connect())
    with database.connect() as conn:
        for default in _DEFAULTS:
            if default["role"] in ("condense", "brief", "brief-upper"):
                body = json.dumps(default)
                store.replace(
                    conn,
                    "prompts",
                    str(default["name"]),
                    body,
                    None,
                    "t",
                    content_hash(body),
                )
        tree = json.loads(store.get(conn, "trees", TREE)["config"])
        body = json.dumps({**tree, "lookups": True})
        store.replace(conn, "trees", TREE, body, None, "t", content_hash(body))
        # what a cold build now does (`cluster/op.py`): a leaf over MAX_CAP
        # is split before any brief, and its children replace it
        model = conn.execute(
            "SELECT model_name FROM embeddings GROUP BY model_name "
            "ORDER BY COUNT(*) DESC LIMIT 1"
        ).fetchone()[0]
        kept: list[int] = []
        pending = list(leaves)
        while pending:
            node = pending.pop(0)
            children = repair.split(conn, TREE, node, model)
            if children:
                print("split", node, "->", children, flush=True)
                pending.extend(children)
            else:
                kept.append(node)
        leaves = kept
        marks = ",".join("?" * len(leaves))
        gone = conn.execute(
            "DELETE FROM condensations WHERE model_name = 'condense-contracts' "
            "AND content_hash IN (SELECT s.content_hash FROM node_members m "
            f"JOIN sections s ON s.id = m.section_id WHERE m.node_id IN ({marks}))",
            leaves,
        ).rowcount
    print("leaves", len(leaves), "condensations dropped", gone, flush=True)
    context = JobContext(database, cache_root=CACHE)
    print("condense", condense(_job("condense", {}), context), flush=True)
    for node in leaves:
        print(node, brief(_job("brief", {"node": node}), context), flush=True)
    with database.connect() as conn:
        ups: dict[int, int] = {}
        frontier = set(leaves)
        while frontier:
            rows = conn.execute(
                "SELECT c.parent_id AS p, n.level AS level FROM node_children c "
                "JOIN nodes n ON n.id = c.parent_id WHERE c.child_id IN "
                f"({','.join('?' * len(frontier))})",
                list(frontier),
            ).fetchall()
            frontier = {int(r["p"]) for r in rows} - set(ups)
            ups.update({int(r["p"]): int(r["level"]) for r in rows})
    for node, level in sorted(ups.items(), key=lambda kv: kv[1]):
        scope = {"level": level, "node": node}
        print(
            node, brief_upper(_job("brief-upper", scope), context), flush=True
        )
    with database.connect() as conn:
        uses = conn.execute(
            "SELECT node_id, file, statement FROM brief_uses ORDER BY node_id"
        ).fetchall()
    exp.save(
        "brief-uses-v9.json",
        [
            {
                "node": u["node_id"],
                "file": u["file"],
                "statement": u["statement"],
            }
            for u in uses
        ],
    )
    print("relations", len(uses), "uppers", len(ups))
    database.close()


def leaves() -> None:
    """Rewrite the sub-tree's leaf briefs, then their uppers, on the built db.

    The condensations stay: only the brief prompt changed (round 12's lookup
    order), so condense would write the same text again.
    """
    database = Database.at(DST)
    with database.connect() as conn:
        for default in _DEFAULTS:
            if default["role"] in ("brief", "brief-upper"):
                body = json.dumps(default)
                store.replace(
                    conn,
                    "prompts",
                    str(default["name"]),
                    body,
                    None,
                    "t",
                    content_hash(body),
                )
        nodes = [
            int(r[0])
            for r in conn.execute(
                "SELECT b.node_id FROM briefs b JOIN nodes n ON n.id = b.node_id "
                "WHERE n.level = 0 AND b.lookups LIKE '%\"calls\"%' "
                "ORDER BY b.node_id"
            )
        ]
    only = [int(a) for a in sys.argv[2:]]  # a pilot: these leaves, no uppers
    context = JobContext(database, cache_root=CACHE)
    for node in only or nodes:
        print(node, brief(_job("brief", {"node": node}), context), flush=True)
    database.close()
    if not only:
        uppers()


def uppers() -> None:
    """Rewrite the sub-tree's upper briefs with the current seeded prompt."""
    database = Database.at(DST)
    with database.connect() as conn:
        default = next(d for d in _DEFAULTS if d["role"] == "brief-upper")
        body = json.dumps(default)
        store.replace(
            conn, "prompts", "brief-upper", body, None, "t", content_hash(body)
        )
        rows = conn.execute(
            "SELECT b.node_id AS node, n.level AS level FROM briefs b "
            "JOIN nodes n ON n.id = b.node_id WHERE n.level > 0 "
            "AND b.created_at > '2026-10-15T14' ORDER BY n.level, b.node_id"
        ).fetchall()
    context = JobContext(database, cache_root=CACHE)
    for row in rows:
        scope = {"level": int(row["level"]), "node": int(row["node"])}
        print(
            row["node"],
            brief_upper(_job("brief-upper", scope), context),
            flush=True,
        )
    database.close()


EXPORT = Path.home() / "hrono-eval" / "export-bcreg-v9-L3"


def export() -> None:
    """hrono's own export of the tree, unpacked where the agents read it."""
    import io
    import shutil
    import tarfile
    import zipfile

    database = Database.at(DST)
    with database.connect() as conn:
        made = saved.build(conn, TREE, 3)
    database.close()
    shutil.rmtree(EXPORT, ignore_errors=True)
    EXPORT.mkdir(parents=True)
    raw = io.BytesIO(made.archive)
    if zipfile.is_zipfile(raw):
        zipfile.ZipFile(raw).extractall(EXPORT)
    else:
        raw.seek(0)
        tarfile.open(fileobj=raw).extractall(EXPORT, filter="data")
    print("files", made.files, "->", EXPORT)


if __name__ == "__main__":
    {"build": build, "leaves": leaves, "uppers": uppers, "export": export}[
        sys.argv[1]
    ]()
