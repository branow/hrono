"""#155: a pinned membership or parenting survives the machine's opinion.

Three places move things, and each had to learn the same rule — `repair`
migrates a misfit member, `levels` re-attaches a misfit child, `settle`
rebuilds the leaf level wholesale. A pin honoured by only one of them is worse
than no pin at all: the edit survives until the next op runs instead of until
the operator changes their mind.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from hrono import pins
from hrono.cluster import store as cluster_store
from hrono.cluster.repair import migrate
from hrono.db.database import Database
from hrono.embed.store import upsert_vector
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash

MODEL = "emb"
TREE = "default"


def _section(conn: object, path: str, body: bytes, vector: list[float]) -> int:
    from hrono.cluster.blend import path_body, register_path_bodies

    digest = content_hash(body)
    istore.upsert_content(conn, digest, body)  # type: ignore[arg-type]
    register_path_bodies(conn, [path])  # type: ignore[arg-type]
    upsert_vector(conn, digest, MODEL, vector)  # type: ignore[arg-type]
    upsert_vector(  # type: ignore[arg-type]
        conn, content_hash(path_body(path)), MODEL, vector
    )
    return istore.insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "ex/repo", path, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )


@pytest.fixture
def db(tmp_path: object) -> Iterator[tuple[Database, int, int, int]]:
    """Two nodes; one member of the first belongs squarely in the second."""
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        stay = _section(conn, "a.py", b"aaa\n", [1.0, 0.0])
        misfit = _section(conn, "b.py", b"bbb\n", [0.0, 1.0])
        other = _section(conn, "c.py", b"ccc\n", [0.0, 1.0])
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [
                (0, stay, False, None),
                (0, misfit, False, None),
                (1, other, False, None),
            ],
            [(stay, [0.1]), (misfit, [0.2]), (other, [0.3])],
        )
        nodes = [
            int(r["id"])
            for r in conn.execute("SELECT id FROM nodes ORDER BY id")
        ]
    yield database, nodes[0], nodes[1], misfit
    database.close()


def _node_of(database: Database, section_id: int) -> int:
    with database.connect() as conn:
        row = conn.execute(
            "SELECT node_id FROM node_members WHERE section_id = ?",
            (section_id,),
        ).fetchone()
    return int(row["node_id"])


def test_migrate_moves_an_unpinned_misfit(
    db: tuple[Database, int, int, int],
) -> None:
    # the control: without a pin this member DOES move, so the next test is
    # measuring the pin and not a migration that never happens.
    database, first, second, misfit = db

    with database.write() as conn:
        moved = migrate(conn, TREE, first, MODEL)

    assert moved == 1
    assert _node_of(database, misfit) == second


def test_a_pinned_member_is_not_migrated(
    db: tuple[Database, int, int, int],
) -> None:
    database, first, _second, misfit = db
    with database.write() as conn:
        pins.pin(conn, pins.MEMBERSHIP, misfit, anchor=first)

    with database.write() as conn:
        moved = migrate(conn, TREE, first, MODEL)

    assert moved == 0
    assert _node_of(database, misfit) == first


def test_unpinning_releases_it_to_the_same_run(
    db: tuple[Database, int, int, int],
) -> None:
    database, first, second, misfit = db
    with database.write() as conn:
        pins.pin(conn, pins.MEMBERSHIP, misfit, anchor=first)
        migrate(conn, TREE, first, MODEL)
    assert _node_of(database, misfit) == first

    with database.write() as conn:
        pins.unpin(conn, pins.MEMBERSHIP, misfit)
        migrate(conn, TREE, first, MODEL)

    assert _node_of(database, misfit) == second


def test_a_pin_records_the_node_it_anchors_to(
    db: tuple[Database, int, int, int],
) -> None:
    # the anchor is not decoration: `settle` rewrites every membership, so by
    # the time it restores the pin there is no current membership to read.
    database, first, _second, misfit = db
    with database.write() as conn:
        pins.pin(conn, pins.MEMBERSHIP, misfit, anchor=first)

    with database.connect() as conn:
        assert pins.anchors(conn, pins.MEMBERSHIP) == {misfit: first}


def test_placement_holds_a_pinned_delta_at_its_anchor(
    db: tuple[Database, int, int, int],
) -> None:
    # the ingest door: reconcile carries a changed section's pin into its
    # delta, and placement must put the chunk at the anchor instead of
    # re-scoring it — the sticky rule and the placement rule are the machine's
    # judgement, and a pin exempts the chunk from both (#154).
    from hrono.cluster.placement import SectionDelta, place

    database, first, second, misfit = db
    with database.write() as conn:
        conn.execute("DELETE FROM node_members WHERE section_id = ?", (misfit,))
        centroids = cluster_store.node_centroids(conn, TREE, MODEL)
        place(
            conn,
            TREE,
            [
                SectionDelta(
                    "changed",
                    _hash_of(conn, misfit),
                    "b.py",
                    section_id=misfit,
                    pinned_anchor=first,
                )
            ],
            centroids,
            MODEL,
            batch=1,
        )

    # scored on similarity it would join `second`; the pin holds it in `first`
    assert _node_of(database, misfit) == first


def test_placement_releases_a_pin_whose_anchor_is_gone(
    db: tuple[Database, int, int, int],
) -> None:
    # a dead anchor has nothing to hold the chunk IN: parking it somewhere
    # nobody chose would hide it, so the pin is released and the normal rule
    # runs.
    from hrono.cluster.placement import SectionDelta, place

    database, first, second, misfit = db
    with database.write() as conn:
        pins.pin(conn, pins.MEMBERSHIP, misfit, anchor=999_999)
        conn.execute("DELETE FROM node_members WHERE section_id = ?", (misfit,))
        centroids = cluster_store.node_centroids(conn, TREE, MODEL)
        place(
            conn,
            TREE,
            [
                SectionDelta(
                    "changed",
                    _hash_of(conn, misfit),
                    "b.py",
                    section_id=misfit,
                    pinned_anchor=999_999,
                )
            ],
            centroids,
            MODEL,
            batch=1,
        )

    assert _node_of(database, misfit) == second  # the normal rule ran
    with database.connect() as conn:
        assert not pins.is_pinned(conn, pins.MEMBERSHIP, misfit)


def test_the_dissolve_sweep_spares_a_node_with_a_pinned_member(
    db: tuple[Database, int, int, int],
) -> None:
    # deleting the other member leaves `first` below two members, which the
    # sweep would dissolve — re-placing the pinned survivor by machine
    # judgement. The pin makes the one-member topic the operator's call.
    from hrono.cluster.placement import SectionDelta, place

    database, first, _second, misfit = db
    with database.write() as conn:
        pins.pin(conn, pins.MEMBERSHIP, misfit, anchor=first)
        stay = conn.execute(
            "SELECT section_id FROM node_members WHERE node_id = ? "
            "AND section_id != ?",
            (first, misfit),
        ).fetchone()
        conn.execute(
            "DELETE FROM node_members WHERE section_id = ?",
            (int(stay["section_id"]),),
        )
        centroids = cluster_store.node_centroids(conn, TREE, MODEL)
        place(
            conn,
            TREE,
            [
                SectionDelta(
                    "deleted",
                    "gone",
                    "a.py",
                    prior_node_id=first,
                )
            ],
            centroids,
            MODEL,
            batch=1,
        )

    with database.connect() as conn:
        alive = conn.execute(
            "SELECT 1 FROM nodes WHERE id = ?", (first,)
        ).fetchone()
    assert alive is not None  # the sweep left the pinned topic standing
    assert _node_of(database, misfit) == first


def _hash_of(conn: object, section_id: int) -> str:
    row = conn.execute(  # type: ignore[attr-defined]
        "SELECT content_hash FROM sections WHERE id = ?", (section_id,)
    ).fetchone()
    return str(row["content_hash"])
