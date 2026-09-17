"""#125: a retired node takes its brief passages with it."""

from collections.abc import Iterator

import pytest

from hrono.cluster import store as cluster_store
from hrono.db.database import Database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.recall import fts
from hrono.recall.brief_passages import store_brief
from hrono.summarize import briefs

TREE = "default"


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
    # #076's collision, from the other direction: the trigger matches on
    # source_type too, so a git source that happens to be called "node-9"
    # survives node 9 being retired.
    database, _kept, going = db
    with database.connect() as conn, conn:
        istore.upsert_content(
            conn, content_hash(b"user body\n"), b"user body\n"
        )
        istore.insert_section(
            conn,
            source=f"node-{going}",  # a USER source with a colliding name
            address=Address("git", "ex/repo", "c.py", "v1"),
            start=0,
            end=10,
            content_hash=content_hash(b"user body\n"),
            ordinal=0,
        )
        fts.index_passage(
            conn,
            passage_id=9999,
            source=f"node-{going}",
            path="c.py",
            body="user body",
        )
    with database.connect() as conn, conn:
        cluster_store.delete_node(conn, going)
    with database.connect() as conn:
        survived = conn.execute(
            "SELECT COUNT(*) FROM sections WHERE source = ? AND "
            "source_type = 'git'",
            (f"node-{going}",),
        ).fetchone()[0]
    assert survived == 1
