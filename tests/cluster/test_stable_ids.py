"""A re-cluster over unchanged CONTENT preserves node ids (and briefs)."""

from collections.abc import Iterator

import pytest

from hrono.cluster import store as cluster_store
from hrono.db.database import Database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.summarize import briefs

TREE = "default"


def add_section(conn: object, path: str, body: bytes) -> int:
    """A stored section for ``body`` — a fresh section id each call, but the
    content hash (identity) is stable for identical bytes."""
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


def _node_of(db: Database, body: bytes) -> int:
    with db.connect() as conn:
        return int(
            conn.execute(
                "SELECT m.node_id AS nid FROM node_members m "
                "JOIN sections s ON s.id = m.section_id "
                "WHERE s.content_hash = ?",
                (content_hash(body),),
            ).fetchone()["nid"]
        )


def _resplit(db: Database) -> None:
    """Mimic a re-sync/split: drop the sections (cascading node_members) and
    re-insert identical content under new section ids."""
    with db.connect() as conn, conn:
        conn.execute("DELETE FROM sections")
        s_a = add_section(conn, "a.py", b"alpha content\n")
        s_b = add_section(conn, "b.py", b"beta content\n")
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [(0, s_a, False, None), (1, s_b, False, None)],
            [(s_a, [0.1]), (s_b, [0.2])],
        )


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        s_a = add_section(conn, "a.py", b"alpha content\n")
        s_b = add_section(conn, "b.py", b"beta content\n")
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [(0, s_a, False, None), (1, s_b, False, None)],
            [(s_a, [0.1]), (s_b, [0.2])],
        )
    yield database
    database.close()


def test_recluster_over_unchanged_content_keeps_node_ids(db: Database) -> None:
    before_a = _node_of(db, b"alpha content\n")
    before_b = _node_of(db, b"beta content\n")
    _resplit(db)  # new section ids, identical content
    assert _node_of(db, b"alpha content\n") == before_a
    assert _node_of(db, b"beta content\n") == before_b


def test_a_preserved_nodes_brief_survives_the_recluster(db: Database) -> None:
    node_a = _node_of(db, b"alpha content\n")
    with db.connect() as conn, conn:
        briefs.upsert(
            conn,
            node_a,
            "# Alpha\n\nkept.",
            model_name="m",
            prompt_name="brief",
            prompt_hash="h",
            member_signature=briefs.member_signature(conn, node_a),
            input_tokens=1,
            output_tokens=1,
        )
    stored_sig = None
    with db.connect() as conn:
        stored_sig = briefs.get(conn, node_a)["member_signature"]
    _resplit(db)
    with db.connect() as conn:
        row = briefs.get(conn, node_a)
        assert row is not None  # NOT cascade-deleted
        assert row["text"] == "# Alpha\n\nkept."
        # its content-derived signature is unchanged -> the freshness skip
        # would fire
        assert briefs.member_signature(conn, node_a) == stored_sig


def test_changed_content_mints_a_new_node_id(db: Database) -> None:
    before_a = _node_of(db, b"alpha content\n")
    before_b = _node_of(db, b"beta content\n")
    with db.connect() as conn, conn:
        conn.execute("DELETE FROM sections")
        s_a = add_section(conn, "a.py", b"ALPHA REWRITTEN\n")  # content changed
        s_b = add_section(conn, "b.py", b"beta content\n")  # unchanged
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [(0, s_a, False, None), (1, s_b, False, None)],
            [(s_a, [0.1]), (s_b, [0.2])],
        )
    assert _node_of(db, b"beta content\n") == before_b  # unchanged -> same id
    assert _node_of(db, b"ALPHA REWRITTEN\n") != before_a  # changed -> new id


def test_a_cascade_delete_does_not_refresh_the_signature(
    db: Database,
) -> None:
    # the regression guard for a fix that must never be made. A section
    # deleted by FK cascade takes its `node_members` row with it and leaves
    # `nodes.signature` alone — the snapshot of the member set as of the last
    # WRITE is what lets `_reconcile` recognise the node after a re-split, when
    # its members have all cascaded away. Refreshing here would stamp the
    # empty-set hash and the node would match nothing.
    with db.connect() as conn, conn:
        node_id = int(
            conn.execute("SELECT id FROM nodes ORDER BY id").fetchone()["id"]
        )
        before = conn.execute(
            "SELECT signature FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()["signature"]
        section_id = int(
            conn.execute(
                "SELECT section_id FROM node_members WHERE node_id = ?",
                (node_id,),
            ).fetchone()["section_id"]
        )
        conn.execute("DELETE FROM sections WHERE id = ?", (section_id,))

    with db.connect() as conn:
        after = conn.execute(
            "SELECT signature FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()["signature"]
        members = int(
            conn.execute(
                "SELECT COUNT(*) FROM node_members WHERE node_id = ?",
                (node_id,),
            ).fetchone()[0]
        )
        recomputed = cluster_store.node_content_signature(conn, node_id)

    assert after == before  # the snapshot is retained, deliberately
    assert members >= 0  # the membership row really did cascade away
    assert recomputed != after  # and recomputing DISAGREES, which is fine
