"""#096: loading a stored tree that is not built to a single root."""

from collections.abc import Iterator

import pytest

from hrono.cluster import store as cluster_store
from hrono.db.database import Database
from hrono.errors import Internal
from hrono.export.store import load
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash

TREE = "default"


def add_section(conn: object, path: str, body: bytes) -> int:
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


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        s0 = add_section(conn, "a.py", b"alpha\n")
        s1 = add_section(conn, "b.py", b"beta\n")
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [(0, s0, False, None), (1, s1, False, None)],
            [(s0, [0.1]), (s1, [0.2])],
        )
    yield database
    database.close()


def _level0(db: Database) -> list[int]:
    with db.connect() as conn:
        return sorted(
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM nodes WHERE tree = ? AND level = 0", (TREE,)
            ).fetchall()
        )


def test_a_forest_is_a_loud_defect(db: Database) -> None:
    # F20: two topics, no level above them. Picking one with max(node_level)
    # served that topic's brief as root.md and dropped the other silently.
    with db.connect() as conn, pytest.raises(Internal) as caught:
        load(conn, TREE)
    assert "single root" in caught.value.message
    assert caught.value.status_code == 500
    assert caught.value.details == {
        "tree": TREE,
        "level": 0,
        "nodes": _level0(db),
    }


def test_a_tree_built_to_one_root_loads(db: Database) -> None:
    level0 = _level0(db)
    with db.connect() as conn, conn:
        cluster_store.replace_level(
            conn,
            TREE,
            1,
            [(0, level0[0], False, None), (0, level0[1], False, None)],
        )
        root = int(
            conn.execute(
                "SELECT id FROM nodes WHERE tree = ? AND level = 1", (TREE,)
            ).fetchone()["id"]
        )
    with db.connect() as conn:
        stored = load(conn, TREE)
    assert stored is not None
    assert stored.root == root
    assert stored.children[root] == tuple(level0)


def test_an_unparented_leaf_below_the_root_still_loads(db: Database) -> None:
    # a leaf the incubator drained in after the build hangs under no parent
    # (#114). That is one node at the top level, not a forest, so export must
    # still work — the orphan is #114's gap, not a reason to refuse the tree.
    level0 = _level0(db)
    with db.connect() as conn, conn:
        cluster_store.replace_level(
            conn, TREE, 1, [(0, level0[0], False, None)]
        )
    with db.connect() as conn:
        stored = load(conn, TREE)
    assert stored is not None
    assert stored.node_level[stored.root] == 1


def test_an_empty_tree_is_still_none(db: Database) -> None:
    with db.connect() as conn:
        assert load(conn, "ghost") is None
