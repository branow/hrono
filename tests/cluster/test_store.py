from collections.abc import Iterator

import pytest

from hrono.cluster import store
from hrono.cluster.blend import path_body, register_path_bodies
from hrono.db.database import Database
from hrono.embed import store as vstore
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash

MODEL = "emb"


def _add_section(conn: object, path: str, body: bytes, ordinal: int) -> int:
    istore.upsert_content(conn, content_hash(body), body)  # type: ignore[arg-type]
    return istore.insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "example.com/repo", path, "v1"),
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=ordinal,
    )


def _embed(conn: object, digest: str, vector: list[float]) -> None:
    vstore.upsert_vector(conn, digest, MODEL, vector)  # type: ignore[arg-type]


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    yield database
    database.close()


def test_combined_vectors_returned_for_fully_embedded_sections(
    db: Database,
) -> None:
    body = b"def f(): return 1\n"
    path = "src/f.py"
    with db.connect() as conn, conn:
        section_id = _add_section(conn, path, body, 0)
        register_path_bodies(conn, [path])
        _embed(conn, content_hash(body), [1.0, 0.0, 0.0, 0.0])
        _embed(conn, content_hash(path_body(path)), [0.0, 1.0, 0.0, 0.0])
    with db.connect() as conn:
        pairs = store.section_combined_vectors(conn, MODEL)
    assert len(pairs) == 1
    returned_id, combined = pairs[0]
    assert returned_id == section_id
    assert len(combined) == 8  # 2x model dims (content ++ path)


def test_sections_missing_a_component_are_skipped(db: Database) -> None:
    body = b"x = 1\n"
    path = "src/x.py"
    with db.connect() as conn, conn:
        _add_section(conn, path, body, 0)
        register_path_bodies(conn, [path])
        # content embedded, path NOT embedded -> no combined vector
        _embed(conn, content_hash(body), [1.0, 0.0, 0.0, 0.0])
    with db.connect() as conn:
        assert store.section_combined_vectors(conn, MODEL) == ()


def test_replace_tree_persists_nodes_members_and_coords(db: Database) -> None:
    with db.connect() as conn, conn:
        s0 = _add_section(conn, "a.py", b"a\n", 0)
        s1 = _add_section(conn, "b.py", b"b\n", 1)
        s2 = _add_section(conn, "c.py", b"c\n", 2)
        members = [
            (0, s0, False, None),
            (0, s1, True, 0.83),
            (1, s2, False, None),
        ]
        coords = [(s0, [0.1] * 3), (s1, [0.2] * 3), (s2, [0.3] * 3)]
        store.replace_tree(conn, "default", 0, members, coords)

    with db.connect() as conn:
        nodes = conn.execute(
            "SELECT id, label FROM nodes WHERE tree='default' AND level=0 "
            "ORDER BY label"
        ).fetchall()
        assert [n["label"] for n in nodes] == [0, 1]
        # every section is a member of exactly one node
        assert (
            conn.execute("SELECT COUNT(*) FROM node_members").fetchone()[0] == 3
        )
        assigned = conn.execute(
            "SELECT section_id, attached, assignment_similarity "
            "FROM node_members ORDER BY section_id"
        ).fetchall()
        by_section = {r["section_id"]: r for r in assigned}
        assert by_section[s1]["attached"] == 1
        assert by_section[s1]["assignment_similarity"] == pytest.approx(0.83)
        assert by_section[s0]["attached"] == 0
        assert by_section[s0]["assignment_similarity"] is None


def test_replace_tree_rebuild_replaces_prior_state(db: Database) -> None:
    with db.connect() as conn, conn:
        s0 = _add_section(conn, "a.py", b"a\n", 0)
        s1 = _add_section(conn, "b.py", b"b\n", 1)
        store.replace_tree(
            conn,
            "default",
            0,
            [(0, s0, False, None), (0, s1, False, None)],
            [(s0, [0.1] * 3), (s1, [0.1] * 3)],
        )
        store.replace_tree(
            conn,
            "default",
            0,
            [(0, s0, False, None), (1, s1, False, None)],
            [(s0, [0.9] * 3), (s1, [0.9] * 3)],
        )
    with db.connect() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE tree='default'"
            ).fetchone()[0]
            == 2
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM section_coords WHERE tree='default'"
            ).fetchone()[0]
            == 2
        )


def test_stored_coords_aligns_or_none(db: Database) -> None:
    with db.connect() as conn, conn:
        s0 = _add_section(conn, "a.py", b"a\n", 0)
        s1 = _add_section(conn, "b.py", b"b\n", 1)
        store.replace_tree(
            conn,
            "default",
            0,
            [(0, s0, False, None), (0, s1, False, None)],
            [(s0, [0.1, 0.2, 0.3]), (s1, [0.4, 0.5, 0.6])],
        )
    with db.connect() as conn:
        aligned = store.stored_coords(conn, "default", [s0, s1])
        assert aligned is not None
        assert aligned[0] == pytest.approx((0.1, 0.2, 0.3))
        assert aligned[1] == pytest.approx((0.4, 0.5, 0.6))
        # a section with no stored coord -> None (fresh init)
        assert store.stored_coords(conn, "default", [s0, s1, 999]) is None


def _placed(conn: object, path: str, body: bytes, vector: list[float]) -> int:
    """An embedded section, ready to be a cluster member."""
    section_id = _add_section(conn, path, body, 0)
    register_path_bodies(conn, [path])  # type: ignore[arg-type]
    _embed(conn, content_hash(body), vector)
    _embed(conn, content_hash(path_body(path)), [0.0, 0.0, 1.0, 0.0])
    return section_id


def test_backfill_gives_a_placed_section_its_cluster_coordinate(
    db: Database,
) -> None:
    # incremental placement produces no UMAP coordinate, so a placed
    # section inherits the one thing that is true of it — the cluster it joined.
    with db.connect() as conn, conn:
        covered = _placed(conn, "a.py", b"alpha\n", [1.0, 0.0, 0.0, 0.0])
        placed = _placed(conn, "b.py", b"beta\n", [1.0, 0.0, 0.0, 0.0])
        store.replace_tree(
            conn,
            "default",
            0,
            [(0, covered, False, None), (0, placed, False, None)],
            [(covered, [1.0, 2.0])],
        )
        assert store.backfill_coords(conn, "default", MODEL) == 1

    with db.connect() as conn:
        aligned = store.stored_coords(conn, "default", [covered, placed])
    assert aligned is not None  # the whole build is covered again
    assert aligned[1] == pytest.approx((1.0, 2.0))


def test_backfill_takes_the_nearest_cluster_when_its_own_has_none(
    db: Database,
) -> None:
    # a drained pool mints a cluster where NOBODY has a coordinate; the nearest
    # cluster that does is the same approximation one level out.
    with db.connect() as conn, conn:
        near = _placed(conn, "a.py", b"alpha\n", [1.0, 0.0, 0.0, 0.0])
        far = _placed(conn, "b.py", b"beta\n", [0.0, 1.0, 0.0, 0.0])
        drained = _placed(conn, "c.py", b"gamma\n", [0.0, 1.0, 0.0, 0.0])
        store.replace_tree(
            conn,
            "default",
            0,
            [(0, near, False, None), (1, far, False, None)],
            [(near, [5.0]), (far, [9.0])],
        )
        store.add_leaf_node(conn, "default", [(drained, False, None)])
        assert store.backfill_coords(conn, "default", MODEL) == 1

    with db.connect() as conn:
        coord = store.stored_coords(conn, "default", [drained])
    assert coord is not None
    assert coord[0] == pytest.approx((9.0,))  # `far`'s cluster, which it fits


def test_backfill_writes_nothing_when_there_is_no_layout_to_preserve(
    db: Database,
) -> None:
    # a first build has no coordinates to inherit; `stored_coords` returning
    # None is then correct, and the caller inits fresh.
    with db.connect() as conn, conn:
        lonely = _placed(conn, "a.py", b"alpha\n", [1.0, 0.0, 0.0, 0.0])
        store.add_leaf_node(conn, "default", [(lonely, False, None)])
        assert store.backfill_coords(conn, "default", MODEL) == 0

    with db.connect() as conn:
        assert store.stored_coords(conn, "default", [lonely]) is None
