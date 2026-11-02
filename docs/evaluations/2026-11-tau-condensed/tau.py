"""Own-centre similarity of the flask copy's placed sections (E056).

Run on a COPY of the flask bench db, after an update placed new sections by
their condensation:

    uv run python docs/evaluations/2026-11-tau-condensed/tau.py .hrono/hrono.db

For every section in a leaf topic of the ``flask`` tree it prints the dot
product of the section's blended condensation vector with its topic's centroid
(the placement rule's own number, ``cluster/placement.py``), and the share of
sections at or above and below TAU. Sections placed by the new update path
are listed on their own, with a check that their clustering vector is the
build's blend of the condensation (not the raw content) vector.
"""

import sys
from pathlib import Path

import numpy as np

from hrono.cluster import store
from hrono.cluster.blend import (
    clustering_vector,
    combined_vector,
    condensation_text,
    folder_vector,
    section_source,
)
from hrono.cluster.placement import TAU
from hrono.db.database import Database
from hrono.embed.store import get_vector
from hrono.ingest.identity import content_hash

TREE = "flask"
MODEL = "emb"  # the registry name of the embedding model


def leave_one_out(conn, rows, centres) -> None:
    """Treat each member as new: take it out of its topic's centroid, place it
    on the best centroid, and count by TAU how many land in their own topic,
    park, or land in another topic."""
    vectors = {}
    for row in rows:
        vector = combined_vector(conn, row["h"], row["path"], MODEL)
        if vector is not None:
            vectors[row["id"]] = (row["node_id"], np.array(vector))
    by_node: dict[int, list[int]] = {}
    for sid, (node, _) in vectors.items():
        by_node.setdefault(node, []).append(sid)
    names = [n for n in centres if n in by_node]
    matrix = np.array([centres[n] for n in names])
    best = []
    for sid, (node, vector) in vectors.items():
        sims = matrix @ vector
        others = [vectors[o][1] for o in by_node[node] if o != sid]
        if others:
            loo = np.mean(others, axis=0)
            sims[names.index(node)] = (loo / np.linalg.norm(loo)) @ vector
        top = int(np.argmax(sims))
        best.append((names[top] == node, float(sims[top])))
    print("leave-one-out placement of every member, by TAU:")
    for tau in (0.55, 0.60, 0.65, 0.70, 0.75):
        right = sum(1 for ok, s in best if ok and s >= tau)
        wrong = sum(1 for ok, s in best if not ok and s >= tau)
        parked = sum(1 for _, s in best if s < tau)
        n = len(best)
        print(
            f"  TAU {tau:.2f}: own topic {right / n:.1%}  "
            f"another topic {wrong / n:.1%}  parked {parked / n:.1%}"
        )


def main(db_path: str, first_new: int = 1410) -> None:
    db = Database.at(Path(db_path))
    with db.connect() as conn:
        centres = store.node_centroids(conn, TREE, MODEL)
        rows = conn.execute(
            "SELECT s.id, s.path, s.content_hash AS h, m.node_id, m.forced "
            "FROM node_members m JOIN sections s ON s.id = m.section_id "
            "JOIN nodes n ON n.id = m.node_id "
            "WHERE n.tree = ? AND n.level = 0",
            (TREE,),
        ).fetchall()
        sims = []
        for row in rows:
            vector = combined_vector(conn, row["h"], row["path"], MODEL)
            if vector is None or row["node_id"] not in centres:
                continue
            centre = centres[row["node_id"]]
            sims.append(sum(a * b for a, b in zip(vector, centre, strict=True)))
        above = sum(1 for s in sims if s >= TAU)
        print(f"sections {len(sims)}  TAU {TAU}")
        print(f"at or above TAU {above} ({above / len(sims):.1%})")
        print(f"below TAU {len(sims) - above} ({1 - above / len(sims):.1%})")
        ordered = sorted(sims)
        for q in (0.05, 0.25, 0.5, 0.75):
            print(f"p{int(q * 100):02d} {ordered[int(q * len(ordered))]:.3f}")
        leave_one_out(conn, rows, centres)
        print(
            "placed by the new update path (sections from id", first_new, "):"
        )
        for row in (r for r in rows if r["id"] >= first_new):
            path = row["path"]
            text = condensation_text(conn, row["h"])
            blend = clustering_vector(
                get_vector(conn, content_hash(text.encode()), MODEL),
                folder_vector(section_source(conn, row["h"], path), path),
            )
            stored = combined_vector(conn, row["h"], path, MODEL)
            same = max(abs(a - b) for a, b in zip(blend, stored, strict=True))
            centre = centres[row["node_id"]]
            sim = sum(a * b for a, b in zip(stored, centre, strict=True))
            print(
                f"  {path}: node {row['node_id']} forced {row['forced']} "
                f"own-centre {sim:.3f} blend-vs-stored {same:.1e}"
            )


if __name__ == "__main__":
    main(sys.argv[1], *map(int, sys.argv[2:]))
