"""Snapshot the state of a hrono database: counts, tree shape, flags.

Usage: python dbstat.py <db_path> [label]
Writes a markdown snapshot to artifacts/snapshots/<label>.md and prints it.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COUNTS = (
    "contents",
    "sections",
    "passages",
    "embeddings",
    "condensations",
    "nodes",
    "node_members",
    "node_children",
    "briefs",
    "section_coords",
    "pending",
    "misfit",
    "tree_batch",
    "update_log",
    "jobs",
)


def rows(conn: sqlite3.Connection, sql: str) -> list[tuple[object, ...]]:
    try:
        return list(conn.execute(sql))
    except sqlite3.Error as exc:
        return [("ERROR", str(exc))]


def main() -> None:
    db_path = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) > 2 else "snapshot"
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    lines = [f"# snapshot: {label}", "", "## row counts", ""]
    for table in COUNTS:
        got = rows(conn, f"SELECT count(*) FROM {table}")
        lines.append(f"- {table}: {got[0][0] if got else '?'}")

    lines += ["", "## nodes per level", ""]
    for row in rows(
        conn,
        "SELECT tree, level, count(*) FROM nodes GROUP BY tree, level "
        "ORDER BY tree, level",
    ):
        lines.append(f"- tree={row[0]} level={row[1]}: {row[2]} nodes")

    lines += ["", "## members per leaf node (level 0)", ""]
    for row in rows(
        conn,
        "SELECT n.id, count(m.section_id), "
        "sum(m.attached), substr(coalesce(n.signature,''),1,12) "
        "FROM nodes n LEFT JOIN node_members m ON m.node_id = n.id "
        "WHERE n.level = 0 GROUP BY n.id ORDER BY n.id",
    ):
        lines.append(
            f"- node {row[0]}: {row[1]} members ({row[2] or 0} attached) "
            f"sig={row[3]}"
        )

    lines += ["", "## briefs", ""]
    for row in rows(
        conn,
        "SELECT b.node_id, n.level, b.model_name, b.prompt_name, "
        "length(b.text), b.input_tokens, b.output_tokens, "
        "coalesce(b.unfaithful, -1) FROM briefs b JOIN nodes n "
        "ON n.id = b.node_id ORDER BY n.level, b.node_id",
    ):
        lines.append(
            f"- node {row[0]} (level {row[1]}): model={row[2]} "
            f"prompt={row[3]} chars={row[4]} in={row[5]} out={row[6]} "
            f"unfaithful={row[7]}"
        )

    lines += ["", "## jobs", ""]
    for row in rows(
        conn,
        "SELECT op, status, count(*), max(updated_at) FROM jobs "
        "GROUP BY op, status ORDER BY max(updated_at)",
    ):
        lines.append(f"- {row[0]} / {row[1]}: {row[2]} (last {row[3]})")

    lines += ["", "## last 15 jobs", ""]
    for row in rows(
        conn,
        "SELECT id, op, status, coalesce(error,''), created_at FROM jobs "
        "ORDER BY created_at DESC LIMIT 15",
    ):
        lines.append(f"- {row[1]} {row[2]} {row[3][:120]} ({row[0][:14]})")

    lines += ["", "## update_log", ""]
    for row in rows(conn, "SELECT * FROM update_log ORDER BY rowid DESC LIMIT 20"):
        lines.append(f"- {row}")

    lines += ["", "## pending (incubator)", ""]
    for row in rows(conn, "SELECT * FROM pending LIMIT 20"):
        lines.append(f"- {row}")

    lines += ["", "## misfit", ""]
    for row in rows(conn, "SELECT * FROM misfit LIMIT 20"):
        lines.append(f"- {row}")

    lines += ["", "## sections per source", ""]
    for row in rows(
        conn,
        "SELECT substr(uri, 1, instr(uri,'://')+2) || "
        "'...', count(*) FROM sections GROUP BY 1",
    ):
        lines.append(f"- {row[0]}: {row[1]}")

    text = "\n".join(lines) + "\n"
    out = ROOT / "artifacts" / "snapshots" / f"{label}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    conn.close()


if __name__ == "__main__":
    main()
