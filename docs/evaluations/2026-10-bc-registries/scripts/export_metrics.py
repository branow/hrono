"""Export one evaluation snapshot of a hrono database to plain files.

Reads the eval server's SQLite file READ-ONLY and writes, under OUT:
jobs.json, calls_by_run.csv, calls_timeline.csv, corpus.csv, tree.json,
refusals.csv, unfaithful.csv and briefs/ (every brief above the leaves, plus a
fixed-seed sample of leaves with their member paths). Nothing secret is read:
users, keys and the registry's encrypted fields are never touched.

usage: python export_metrics.py <hrono.db> <tree> <out dir>
"""

from __future__ import annotations

import csv
import json
import random
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

LEAF_SAMPLE = 25


def main(db: Path, tree: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    _jobs(conn, out)
    _calls(conn, out)
    _corpus(conn, out)
    _tree(conn, tree, out)
    _refusals(conn, out)
    _briefs(conn, tree, out)


def _jobs(conn: sqlite3.Connection, out: Path) -> None:
    rows = conn.execute(
        "SELECT id, parent_id, tree, op, status, error, error_code, "
        "error_details, attempts, created_at, updated_at, result "
        "FROM jobs ORDER BY created_at"
    ).fetchall()
    jobs = [
        {
            **{k: row[k] for k in row.keys() if k not in ("result",)},
            "error_details": _json(row["error_details"]),
            "result": _json(row["result"]),
        }
        for row in rows
    ]
    (out / "jobs.json").write_text(json.dumps(jobs, indent=2) + "\n")


def _calls(conn: sqlite3.Connection, out: Path) -> None:
    _csv(
        out / "calls_by_run.csv",
        conn.execute(
            "SELECT run_id, role, model, provider, upstream_model, "
            "COUNT(*) AS calls, SUM(1 - ok) AS failed, "
            "SUM(input_tokens) AS input, SUM(output_tokens) AS output, "
            "SUM(cache_read_tokens) AS cache_read, "
            "SUM(cache_creation_tokens) AS cache_write, "
            "ROUND(SUM(duration_ms) / 1000.0, 1) AS model_seconds, "
            "ROUND(AVG(duration_ms) / 1000.0, 1) AS avg_seconds, "
            "MAX(duration_ms) / 1000 AS max_seconds, "
            "MIN(created_at) AS first, MAX(created_at) AS last "
            "FROM llm_calls GROUP BY run_id, role, model "
            "ORDER BY first"
        ),
    )
    _csv(
        out / "calls_timeline.csv",
        conn.execute(
            "SELECT SUBSTR(created_at, 1, 15) || '0' AS ten_minutes_utc, "
            "role, COUNT(*) AS calls, SUM(ok) AS ok, "
            "ROUND(AVG(duration_ms) / 1000.0, 1) AS avg_seconds, "
            "SUM(output_tokens) AS output "
            "FROM llm_calls WHERE role != 'embedding' "
            "GROUP BY 1, role ORDER BY 1"
        ),
    )


def _corpus(conn: sqlite3.Connection, out: Path) -> None:
    _csv(
        out / "corpus.csv",
        conn.execute(
            "SELECT s.source, "
            "CASE WHEN INSTR(s.path, '/') > 0 "
            "THEN SUBSTR(s.path, 1, INSTR(s.path, '/') - 1) "
            "ELSE '.' END AS top_dir, "
            "COUNT(*) AS sections, COUNT(DISTINCT s.path) AS files, "
            "SUM(LENGTH(c.body)) AS bytes "
            "FROM sections s JOIN contents c "
            "ON c.content_hash = s.content_hash "
            "WHERE s.source_type != 'node' GROUP BY 1, 2 ORDER BY 3 DESC"
        ),
    )


def _tree(conn: sqlite3.Connection, tree: str, out: Path) -> None:
    levels = dict(
        conn.execute(
            "SELECT level, COUNT(*) FROM nodes WHERE tree = ? GROUP BY level",
            (tree,),
        ).fetchall()
    )
    members: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for node, source, attached in conn.execute(
        "SELECT m.node_id, s.source, m.attached FROM node_members m "
        "JOIN sections s ON s.id = m.section_id "
        "JOIN nodes n ON n.id = m.node_id WHERE n.tree = ?",
        (tree,),
    ):
        members[node].append((source, attached))
    leaves = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM nodes WHERE tree = ? AND level = 0", (tree,)
        )
    ]
    sizes = sorted(len(members[leaf]) for leaf in leaves)
    total = sum(sizes) or 1
    shape = {
        "nodes_per_level": {str(k): v for k, v in sorted(levels.items())},
        "sections": conn.execute(
            "SELECT COUNT(*) FROM sections WHERE source_type != 'node'"
        ).fetchone()[0],
        "pending": conn.execute(
            "SELECT COUNT(*) FROM pending WHERE tree = ?", (tree,)
        ).fetchone()[0],
        "leaf_size": {
            "min": sizes[0] if sizes else 0,
            "median": statistics.median(sizes) if sizes else 0,
            "p90": sizes[int(0.9 * len(sizes))] if sizes else 0,
            "max": sizes[-1] if sizes else 0,
            "over_cap_30": sum(size > 30 for size in sizes),
            "histogram": dict(Counter(min(s // 5 * 5, 60) for s in sizes)),
        },
        "attached_share": round(
            sum(a for leaf in leaves for _, a in members[leaf]) / total, 4
        ),
        "leaves_spanning_repos": sum(
            len({s for s, _ in members[leaf]}) > 1 for leaf in leaves
        ),
        "children_per_parent": _fanout(conn, tree),
    }
    (out / "tree.json").write_text(json.dumps(shape, indent=2) + "\n")


def _fanout(conn: sqlite3.Connection, tree: str) -> dict[str, list[int]]:
    rows = conn.execute(
        "SELECT n.level, COUNT(c.child_id) FROM nodes n "
        "JOIN node_children c ON c.parent_id = n.id WHERE n.tree = ? "
        "GROUP BY n.id ORDER BY n.level DESC",
        (tree,),
    ).fetchall()
    fanout: dict[str, list[int]] = defaultdict(list)
    for level, count in rows:
        fanout[str(level)].append(count)
    return {level: sorted(counts) for level, counts in fanout.items()}


def _refusals(conn: sqlite3.Connection, out: Path) -> None:
    _csv(
        out / "refusals.csv",
        conn.execute(
            "SELECT r.reason, s.source, s.path, r.refused_at "
            "FROM condense_refusals r JOIN sections s "
            "ON s.content_hash = r.content_hash GROUP BY r.content_hash"
        ),
    )
    _csv(
        out / "unfaithful.csv",
        conn.execute(
            "SELECT n.level, b.node_id, b.unfaithful FROM briefs b "
            "JOIN nodes n ON n.id = b.node_id WHERE b.unfaithful != '[]' "
            "ORDER BY n.level DESC, b.node_id"
        ),
    )


def _briefs(conn: sqlite3.Connection, tree: str, out: Path) -> None:
    folder = out / "briefs"
    folder.mkdir(exist_ok=True)
    upper = conn.execute(
        "SELECT n.id, n.level, b.text FROM nodes n JOIN briefs b "
        "ON b.node_id = n.id WHERE n.tree = ? AND n.level > 0 "
        "ORDER BY n.level DESC, n.id",
        (tree,),
    ).fetchall()
    for row in upper:
        children = [
            r[0]
            for r in conn.execute(
                "SELECT child_id FROM node_children WHERE parent_id = ?",
                (row["id"],),
            )
        ]
        (folder / f"L{row['level']}-node{row['id']}.md").write_text(
            f"<!-- level {row['level']}, node {row['id']}, "
            f"children {children} -->\n\n{row['text']}\n"
        )
    leaves = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM nodes WHERE tree = ? AND level = 0 ORDER BY id",
            (tree,),
        )
    ]
    for leaf in random.Random(7).sample(leaves, min(LEAF_SAMPLE, len(leaves))):
        text = conn.execute(
            "SELECT text FROM briefs WHERE node_id = ?", (leaf,)
        ).fetchone()
        paths = [
            f"- {r[0]}: {r[1]}"
            for r in conn.execute(
                "SELECT s.source, s.path FROM node_members m JOIN sections s "
                "ON s.id = m.section_id WHERE m.node_id = ? ORDER BY 1, 2",
                (leaf,),
            )
        ]
        (folder / f"L0-node{leaf}.md").write_text(
            f"<!-- leaf {leaf}, {len(paths)} members -->\n\n"
            f"{text[0] if text else '(no brief)'}\n\n## Members\n\n"
            + "\n".join(paths)
            + "\n"
        )


def _csv(path: Path, cursor: sqlite3.Cursor) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([d[0] for d in cursor.description])
        writer.writerows(cursor.fetchall())


def _json(text: str | None) -> object:
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return text


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]))
