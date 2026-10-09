"""What warm init is FOR — unchanged content keeps its place.

The warm path (`backfill_coords` gives every placed section a coordinate, so
`stored_coords` does not return None) has tests that assert the mechanism:
coverage, and an `init` that arrives non-None. This drives the whole warm path
over the REAL recipe (no injected build seam) — build, add
sections, place them, backfill, rebuild — and asserts the property the mechanism
exists to deliver: after the rebuild, unchanged sections are still with the same
neighbours, and nobody has fallen out of the map.

Measured on this fixture (60 planted sections in 5 groups, 6 added and placed,
one warm rebuild):

    unchanged sections keeping their topic, WARM init : 60 / 60  (1.000)
    unchanged sections keeping their topic, COLD init : 60 / 60  (1.000)
    topics before -> after: 5 -> 5

FLOOR is 0.90, a measured 1.000 minus room for the jitter of a different
numba/UMAP build; a 5-topic partition drawn at random agrees at ~0.2.

What this does NOT show, stated so no future reader assumes otherwise: the
floor is insensitive to the init. Mutating the warm path and re-running this
test — misaligning the stored coords to their sections, backfilling zeros,
backfilling the cluster mean times a thousand, or dropping the init entirely —
leaves stability at 1.000 every time, and so does mutating the recipe itself
(min_cluster_size 5 -> 20, n_components 25 -> 2). On a corpus of separated
topics the partition simply does not depend on where UMAP starts. Measured on
a harder corpus (240 points, 8 groups, spread 0.3-0.5) warm and cold agree
inside the noise, and warm is not reliably the better of the two: 0.850 vs
0.863 on one seed, 0.950 vs 0.950 on the next.

So the assertions with teeth here are the warm path's own mechanism end to end
— the backfill covering every new section, `stored_coords` going warm because
of it, and the rebuild keeping everyone placed. Each of those three is killed
by mutating exactly the code it names. The stability floor rides along as the
property statement and a guard against a rebuild that scrambles the map; the
benefit of warm init over cold remains unproven, which is a measurement rather
than a suspicion.

Slow by nature: two real UMAP builds, a few seconds each.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pytest

from hrono.cluster import op as cluster_op
from hrono.cluster import placement, store
from hrono.cluster.build import build_clusters
from hrono.db.database import Database
from tests.cluster.test_op import (
    MODEL,
    add_planted_section,
    cluster_job,
    register_model,
)

FLOOR = 0.90
PLANTED = 60
GROUPS = 5
ADDED = 6
DIM = 16


def _corpus(seed: int = 0) -> tuple[list[list[float]], list[list[float]]]:
    """``PLANTED`` unit vectors in GROUPS blobs, plus ``ADDED`` later ones."""
    rng = np.random.default_rng(seed)
    centres = []
    for _ in range(GROUPS):
        centre = rng.normal(size=DIM)
        centres.append(centre / np.linalg.norm(centre))

    def near(centre: np.ndarray, spread: float) -> list[float]:
        point = centre + spread * rng.normal(size=DIM)
        return (point / np.linalg.norm(point)).tolist()

    planted = [near(centres[i % GROUPS], 0.10) for i in range(PLANTED)]
    added = [near(centres[i % GROUPS], 0.10) for i in range(ADDED)]
    return planted, added


def _membership(database: Database) -> dict[int, int]:
    """section id -> its level-0 node id."""
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT m.section_id AS s, m.node_id AS n FROM node_members m "
            "JOIN nodes ON nodes.id = m.node_id "
            "WHERE nodes.tree = 'default' AND nodes.level = 0"
        ).fetchall()
    return {int(row["s"]): int(row["n"]) for row in rows}


def _kept(
    before: dict[int, int], after: dict[int, int], sections: list[int]
) -> float:
    """Fraction of ``sections`` whose topic survives, up to renaming.

    Node ids are rewritten by every full build, so "the same topic" can only
    mean "still with the same neighbours": each old topic is matched to the new
    topic holding most of its members, and a member elsewhere is one that moved.
    """
    groups: dict[int, list[int]] = {}
    for section in sections:
        groups.setdefault(before[section], []).append(section)
    kept = 0
    for members in groups.values():
        landed: dict[int, int] = {}
        for section in members:
            node = after[section]
            landed[node] = landed.get(node, 0) + 1
        kept += max(landed.values())
    return kept / len(sections)


def _place(database: Database, section_ids: list[int]) -> None:
    """The real incremental path: assign each new section, then backfill."""
    with database.write() as conn:
        centroids = store.node_centroids(conn, "default", MODEL)
        for section_id in section_ids:
            row = conn.execute(
                "SELECT content_hash, path FROM sections WHERE id = ?",
                (section_id,),
            ).fetchone()
            placement.assign_or_park(
                conn,
                "default",
                section_id=section_id,
                content_hash=str(row["content_hash"]),
                path=str(row["path"]),
                centroids=centroids,
                model_name=MODEL,
                batch=1,
            )
        written = store.backfill_coords(conn, "default", MODEL)
    assert written == len(section_ids)  # the warm path can now fire at all


@pytest.fixture
def planted(tmp_path: object) -> Iterator[tuple[Database, list[list[float]]]]:
    database = Database.at(tmp_path / "hrono.db")
    vectors, added = _corpus()
    with database.connect() as conn, conn:
        register_model(conn)
        for i, vector in enumerate(vectors):
            add_planted_section(conn, "repo-a", i, vector)
    yield database, added
    database.close()


def test_a_warm_rebuild_keeps_unchanged_sections_in_their_topic(
    planted: tuple[Database, list[list[float]]],
) -> None:
    database, added = planted
    context = cluster_op.JobContext(database)
    first = cluster_op.cluster(cluster_job("c1"), context, build=build_clusters)
    before = _membership(database)
    original = sorted(before)
    assert len(original) == PLANTED

    with database.write() as conn:
        new_ids = [
            add_planted_section(conn, "repo-b", i, vector)
            for i, vector in enumerate(added)
        ]
    _place(database, new_ids)

    with database.connect() as conn:
        pairs = store.section_combined_vectors(conn, MODEL)
        init = store.stored_coords(conn, "default", tuple(s for s, _ in pairs))
    assert init is not None  # warm, not cold: every section has a coordinate

    second = cluster_op.cluster(
        cluster_job("c2"), context, build=build_clusters
    )
    after = _membership(database)

    assert _kept(before, after, original) >= FLOOR
    assert len(after) == PLANTED + ADDED  # everyone is still placed
    assert abs(int(second["topics"]) - int(first["topics"])) <= 1
