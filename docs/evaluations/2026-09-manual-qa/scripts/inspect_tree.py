"""Print the built tree: levels, children, members, brief heads, flags.

Usage: python inspect_tree.py <db_path> <tree> [label]
Writes artifacts/tree-<label>.md.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    db_path = sys.argv[1]
    tree = sys.argv[2] if len(sys.argv) > 2 else "default"
    label = sys.argv[3] if len(sys.argv) > 3 else "tree"
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    out: list[str] = [f"# tree `{tree}` structure", ""]

    levels = list(
        conn.execute(
            "SELECT level, count(*) n FROM nodes WHERE tree=? "
            "GROUP BY level ORDER BY level",
            (tree,),
        )
    )
    out += ["## levels", ""]
    for row in levels:
        out.append(f"- level {row['level']}: {row['n']} nodes")
    out.append("")

    children = {
        row["parent_id"]: row["kids"]
        for row in conn.execute(
            "SELECT parent_id, count(*) kids FROM node_children GROUP BY 1"
        )
    }

    for row in levels:
        level = row["level"]
        out += [f"## level {level}", ""]
        for node in conn.execute(
            "SELECT n.id, n.label, n.signature, "
            "(SELECT count(*) FROM node_members m WHERE m.node_id=n.id) mem, "
            "(SELECT count(*) FROM node_members m WHERE m.node_id=n.id "
            " AND m.attached=1) att, "
            "(SELECT count(*) FROM node_members m WHERE m.node_id=n.id "
            " AND m.forced=1) forced, "
            "b.text, b.stale, b.unfaithful, b.model_name, b.prompt_name "
            "FROM nodes n LEFT JOIN briefs b ON b.node_id=n.id "
            "WHERE n.tree=? AND n.level=? ORDER BY n.id",
            (tree, level),
        ):
            head = (node["text"] or "").strip().splitlines()
            title = head[0][:120] if head else "(no brief)"
            out.append(
                f"### node {node['id']} (label {node['label']}) — "
                f"{node['mem']} members, {node['att']} attached, "
                f"{node['forced']} forced, "
                f"{children.get(node['id'], 0)} children, "
                f"stale={node['stale']} unfaithful={node['unfaithful']}"
            )
            out.append(f"  sig={(node['signature'] or '')[:16]}")
            out.append(f"  brief: {title}")
            if level == 0:
                paths = [
                    r["path"]
                    for r in conn.execute(
                        "SELECT DISTINCT s.path FROM node_members m "
                        "JOIN sections s ON s.id=m.section_id "
                        "WHERE m.node_id=? ORDER BY s.path LIMIT 8",
                        (node["id"],),
                    )
                ]
                out.append(f"  member paths: {', '.join(paths)}")
            else:
                kids = [
                    str(r["child_id"])
                    for r in conn.execute(
                        "SELECT child_id FROM node_children WHERE parent_id=? "
                        "ORDER BY child_id",
                        (node["id"],),
                    )
                ]
                out.append(f"  child nodes: {', '.join(kids)}")
            out.append("")

    unclustered = conn.execute(
        "SELECT count(*) FROM sections s WHERE s.id NOT IN "
        "(SELECT section_id FROM node_members)"
    ).fetchone()[0]
    parked = conn.execute(
        "SELECT count(*) FROM pending WHERE tree=?", (tree,)
    ).fetchone()[0]
    out += [
        "## invariants",
        "",
        f"- sections in no node: {unclustered}",
        f"- sections parked in the incubator: {parked}",
        f"- total sections: "
        f"{conn.execute('SELECT count(*) FROM sections').fetchone()[0]}",
        "",
    ]

    text = "\n".join(out)
    (ROOT / "artifacts" / f"tree-{label}.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
