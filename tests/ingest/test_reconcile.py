"""T34 reconcile: file diff -> section-store mutation + section deltas."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster import store as cluster_store
from hrono.db.database import Database
from hrono.ingest import reconcile
from hrono.ingest.diff import Change

SOURCE = "repo"
TREE = "default"
COMMON = dict(
    tree=TREE,
    source=SOURCE,
    source_type="git",
    instance="ex/repo",
    version="v1",
)


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    root = tmp_path / "cache"
    root.mkdir()
    return root


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    yield database
    database.close()


def _write(cache: Path, path: str, text: str) -> None:
    (cache / path).write_text(text)


def _hashes(db: Database, path: str) -> set[str]:
    with db.connect() as conn:
        return {
            r["content_hash"]
            for r in conn.execute(
                "SELECT content_hash FROM sections WHERE path = ?", (path,)
            ).fetchall()
        }


def _seed(db: Database, cache: Path, path: str, text: str) -> int:
    """Store an initial file and cluster its sections; return the node id."""
    _write(cache, path, text)
    with db.connect() as conn, conn:
        deltas = reconcile.reconcile(
            conn, **COMMON, cache=cache, changes=[Change(path, "new")]
        )
        sids = [d.section_id for d in deltas if d.section_id is not None]
        return cluster_store.add_leaf_node(
            conn, TREE, [(s, False, None) for s in sids]
        )


def test_new_file_stores_sections_and_new_deltas(
    db: Database, cache: Path
) -> None:
    _write(cache, "f.txt", "alpha content here\n")
    with db.connect() as conn, conn:
        deltas = reconcile.reconcile(
            conn, **COMMON, cache=cache, changes=[Change("f.txt", "new")]
        )
    assert deltas and all(d.kind == "new" for d in deltas)
    assert all(d.prior_node_id is None for d in deltas)
    assert _hashes(db, "f.txt")


def test_changed_file_swaps_content_and_carries_prior_node(
    db: Database, cache: Path
) -> None:
    node = _seed(db, cache, "f.txt", "alpha content here\n")
    old = _hashes(db, "f.txt")
    _write(cache, "f.txt", "beta rewritten content\n")
    with db.connect() as conn, conn:
        deltas = reconcile.reconcile(
            conn, **COMMON, cache=cache, changes=[Change("f.txt", "changed")]
        )
    new = _hashes(db, "f.txt")
    assert new and new != old  # content swapped in the store
    changed = [d for d in deltas if d.kind == "changed"]
    assert changed and all(d.prior_node_id == node for d in changed)


def test_deleted_file_removes_sections_and_emits_deleted(
    db: Database, cache: Path
) -> None:
    node = _seed(db, cache, "f.txt", "alpha content here\n")
    with db.connect() as conn, conn:
        deltas = reconcile.reconcile(
            conn, **COMMON, cache=cache, changes=[Change("f.txt", "deleted")]
        )
    assert not _hashes(db, "f.txt")  # gone from the store
    assert deltas and all(
        d.kind == "deleted" and d.prior_node_id == node for d in deltas
    )


def test_moved_file_reuses_content_hash_under_new_path(
    db: Database, cache: Path
) -> None:
    node = _seed(db, cache, "old.txt", "portable content\n")
    old_hashes = _hashes(db, "old.txt")
    _write(cache, "new.txt", "portable content\n")  # identical bytes
    with db.connect() as conn, conn:
        deltas = reconcile.reconcile(
            conn,
            **COMMON,
            cache=cache,
            changes=[Change("new.txt", "moved", old_path="old.txt")],
        )
    assert not _hashes(db, "old.txt")  # old path emptied
    assert _hashes(db, "new.txt") == old_hashes  # content reused, not re-hashed
    moved = [d for d in deltas if d.kind == "moved"]
    assert moved and all(d.prior_node_id == node for d in moved)


def test_a_move_that_re_splits_the_file_is_a_change_not_a_move(
    db: Database, cache: Path
) -> None:
    # placement keeps a `moved` section in its node untouched, which is only
    # sound because a move means identical CONTENT. A rename that changes the
    # extension re-splits under a different budget, so the sections that come
    # out are new content and must take the sticky re-check instead (#100).
    body = "".join(
        f'  {{"i": {i}, "text": "padding value"}},\n' for i in range(160)
    )
    node = _seed(db, cache, "data.md", body)
    _write(cache, "data.json", body)
    with db.connect() as conn, conn:
        deltas = reconcile.reconcile(
            conn,
            **COMMON,
            cache=cache,
            changes=[Change("data.json", "moved", old_path="data.md")],
        )
    kinds = {d.kind for d in deltas if d.section_id is not None}
    assert len(_hashes(db, "data.json")) > 1  # the 2 KB data budget re-split it
    assert "changed" in kinds  # the re-split slices are not the same content
    assert all(
        d.prior_node_id in (node, None)
        for d in deltas
        if d.section_id is not None
    )


def test_a_moved_delta_carries_the_membership_it_had(
    db: Database, cache: Path
) -> None:
    node = _seed(db, cache, "old.txt", "portable content\n")
    with db.connect() as conn, conn:
        section = next(
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM sections WHERE path = 'old.txt'"
            ).fetchall()
        )
        conn.execute(
            "UPDATE node_members SET assignment_similarity = 0.77, forced = 1 "
            "WHERE section_id = ?",
            (section,),
        )
    _write(cache, "new.txt", "portable content\n")
    with db.connect() as conn, conn:
        deltas = reconcile.reconcile(
            conn,
            **COMMON,
            cache=cache,
            changes=[Change("new.txt", "moved", old_path="old.txt")],
        )
    moved = [d for d in deltas if d.kind == "moved"]
    assert moved
    assert all(d.prior_node_id == node for d in moved)
    assert all(d.prior_similarity == 0.77 for d in moved)
    assert all(d.prior_forced for d in moved)
