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
