"""A retired node takes its brief passages with it."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster import store as cluster_store
from hrono.db import migrations
from hrono.db.connection import connect
from hrono.db.database import Database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.recall import fts
from hrono.recall.brief_passages import store_brief
from hrono.summarize import briefs

TREE = "default"
SWEEP = 25  # the migration whose one-off half this file pins


def _section(conn: object, path: str, body: bytes) -> int:
    istore.upsert_content(conn, content_hash(body), body)  # type: ignore[arg-type]
    return istore.insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "ex/repo", path, "v1"),
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=0,
    )


def _brief(conn: object, node_id: int, text: str) -> None:
    briefs.upsert(
        conn,  # type: ignore[arg-type]
        node_id,
        text,
        model_name="m",
        prompt_name="brief",
        prompt_hash="h",
        member_signature="sig",
        input_tokens=1,
        output_tokens=1,
    )
    store_brief(conn, node_id, text, "sig")  # type: ignore[arg-type]


def _brief_passages(db: Database, node_id: int) -> tuple[int, int]:
    with db.connect() as conn:
        sections = conn.execute(
            "SELECT COUNT(*) FROM sections WHERE source = ?",
            (f"node-{node_id}",),
        ).fetchone()[0]
        indexed = conn.execute(
            "SELECT COUNT(*) FROM passages_fts WHERE source = ?",
            (f"node-{node_id}",),
        ).fetchone()[0]
    return int(sections), int(indexed)


def _user_source(conn: sqlite3.Connection, source: str) -> int:
    """A git source whose NAME collides with a node's; return its id."""
    body = b"user body\n"
    address = Address("git", "ex/repo", "c.py", "v1")
    istore.upsert_content(conn, content_hash(body), body)
    section = istore.insert_section(
        conn,
        source=source,
        address=address,
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=0,
    )
    passage = istore.insert_passage(
        conn,
        section_id=section,
        source=source,
        address=address,
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        sp_paths=(),
        ordinal=0,
    )
    fts.index_passage(
        conn,
        passage_id=passage,
        source=source,
        path="c.py",
        body=body.decode(),
    )
    return passage


def _orphan_brief(conn: sqlite3.Connection, node_id: int) -> None:
    """A node:// brief whose node is gone — a past rebuild's leftover."""
    body = b"a topic the map no longer contains\n"
    address = Address("node", "hrono", f"nodes/{node_id}/topic", "sig")
    source = f"node-{node_id}"
    istore.upsert_content(conn, content_hash(body), body)
    section = istore.insert_section(
        conn,
        source=source,
        address=address,
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=0,
    )
    passage = istore.insert_passage(
        conn,
        section_id=section,
        source=source,
        address=address,
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        sp_paths=(),
        ordinal=0,
    )
    fts.index_passage(
        conn,
        passage_id=passage,
        source=source,
        path=address.path,
        body=body.decode(),
    )


def _indexed(conn: sqlite3.Connection, source: str) -> tuple[int, ...]:
    """Passage ids the keyword index still holds for ``source``, dangling ones
    included — a count joined back to `passages` cannot see a row whose passage
    has cascaded away, which is the orphan this migration exists to remove."""
    rows = conn.execute(
        "SELECT passage_id FROM passages_fts WHERE source = ? "
        "ORDER BY passage_id",
        (source,),
    ).fetchall()
    return tuple(int(row["passage_id"]) for row in rows)


def _counts(
    conn: sqlite3.Connection, source: str, source_type: str
) -> tuple[int, int, int]:
    return tuple(  # type: ignore[return-value]
        conn.execute(sql, (source, source_type)).fetchone()[0]
        for sql in (
            "SELECT COUNT(*) FROM sections "
            "WHERE source = ? AND source_type = ?",
            "SELECT COUNT(*) FROM passages "
            "WHERE source = ? AND source_type = ?",
            "SELECT COUNT(*) FROM passages_fts f WHERE f.source = ? "
            "AND EXISTS (SELECT 1 FROM passages p WHERE p.id = f.passage_id "
            "            AND p.source_type = ?)",
        )
    )


@pytest.fixture
def db(tmp_path: object) -> Iterator[tuple[Database, int, int]]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        kept = _section(conn, "a.py", b"alpha content that stays\n")
        going = _section(conn, "b.py", b"beta content that goes away\n")
        node_kept = cluster_store.add_leaf_node(
            conn, TREE, [(kept, False, None)]
        )
        node_going = cluster_store.add_leaf_node(
            conn, TREE, [(going, False, None)]
        )
        _brief(conn, node_kept, "The alpha topic, which survives the rebuild.")
        _brief(conn, node_going, "The beta topic, retired by the rebuild.")
    yield database, node_kept, node_going
    database.close()


def test_deleting_a_node_takes_its_brief_passages(
    db: tuple[Database, int, int],
) -> None:
    database, kept, going = db
    assert _brief_passages(database, going) > (0, 0)

    with database.connect() as conn, conn:
        cluster_store.delete_node(conn, going)

    assert _brief_passages(database, going) == (0, 0)
    assert _brief_passages(database, kept) > (0, 0)  # never the live one


def test_a_rebuild_that_retires_a_node_leaves_no_orphans(
    db: tuple[Database, int, int],
) -> None:
    # the real path: replace_tree re-derives level 0, a label matches nothing,
    # and _reconcile retires that node. Its summary must not outlive it.
    database, kept, going = db
    with database.connect() as conn, conn:
        survivor = conn.execute(
            "SELECT section_id FROM node_members WHERE node_id = ?", (kept,)
        ).fetchone()["section_id"]
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [(0, int(survivor), False, None)],
            [(int(survivor), [0.1])],
        )

    with database.connect() as conn:
        orphans = conn.execute(
            "SELECT COUNT(*) FROM sections s WHERE s.source_type = 'node' "
            "AND NOT EXISTS (SELECT 1 FROM nodes n "
            "                WHERE 'node-' || n.id = s.source)"
        ).fetchone()[0]
    assert orphans == 0
    assert _brief_passages(database, going) == (0, 0)


def test_dropping_a_whole_level_takes_its_brief_passages(
    db: tuple[Database, int, int],
) -> None:
    # build_tree drops a level that did not reduce the node count — a third
    # retirement site, and the one a per-call-site cleanup would have missed.
    database, kept, going = db
    with database.connect() as conn, conn:
        conn.execute("DELETE FROM nodes WHERE tree = ? AND level = 0", (TREE,))
    assert _brief_passages(database, kept) == (0, 0)
    assert _brief_passages(database, going) == (0, 0)


def test_a_user_source_named_like_a_node_is_untouched(
    db: tuple[Database, int, int],
) -> None:
    # the name collision, from the other direction: the trigger matches on
    # source_type too, so a git source that happens to be called "node-9"
    # survives node 9 being retired.
    database, _kept, going = db
    with database.connect() as conn, conn:
        user = _user_source(conn, f"node-{going}")
    with database.connect() as conn, conn:
        cluster_store.delete_node(conn, going)

    # all three halves, and through a REAL passage row: the FTS delete reaches
    # its rows through `passages`, so a phantom passage id would survive every
    # form of that subquery and prove nothing about the source_type guard.
    with database.connect() as conn:
        assert _counts(conn, f"node-{going}", "git") == (1, 1, 1)
        assert _indexed(conn, f"node-{going}") == (user,)


def test_the_sweep_clears_existing_orphans_and_spares_a_colliding_source(
    tmp_path: Path,
) -> None:
    # the one-off half of 0025, which the trigger cannot cover: a database
    # built BEFORE it already carries the orphans of every past rebuild.
    earlier = tuple(m for m in migrations.packaged() if m.version < SWEEP)
    conn = connect(tmp_path / "hrono.db")
    migrations.Migrator(earlier).apply(conn)
    with conn:
        user = _user_source(conn, "node-99")
        _orphan_brief(conn, 99)

    applied = migrations.migrate(conn)  # the real entry point, not the SQL

    assert SWEEP in applied
    assert _counts(conn, "node-99", "node") == (0, 0, 0)
    assert _counts(conn, "node-99", "git") == (1, 1, 1)
    assert _indexed(conn, "node-99") == (user,)
    conn.close()
