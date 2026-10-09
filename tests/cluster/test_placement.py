"""The incremental placement rule — sticky, nearest-centroid, dissolve."""

from collections.abc import Iterator

import pytest

from hrono.cluster import incubator, placement
from hrono.cluster import store as cluster_store
from hrono.cluster.blend import path_body, register_path_bodies
from hrono.cluster.placement import SectionDelta
from hrono.db.database import Database
from hrono.embed.store import upsert_vector
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content

MODEL = "emb"
DIMS = 4
PATH = "src/x.py"
TREE = "default"


def unit(i: int) -> list[float]:
    v = [0.0] * DIMS
    v[i] = 1.0
    return v


def add_section(conn: object, body: bytes, vec: list[float]) -> tuple[int, str]:
    digest = content_hash(body)
    upsert_content(conn, digest, body)  # type: ignore[arg-type]
    upsert_vector(conn, digest, MODEL, vec)  # type: ignore[arg-type]
    section_id = insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "ex/repo", PATH, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )
    return section_id, digest


def make_node(conn: object, topic: int, n: int) -> tuple[int, list[int]]:
    members = []
    for i in range(n):
        sid, _ = add_section(conn, f"t{topic}-m{i}\n".encode(), unit(topic))
        members.append(sid)
    node_id = cluster_store.add_leaf_node(
        conn, TREE, [(s, False, None) for s in members]
    )
    return node_id, members


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register_path_bodies(conn, [PATH])
        upsert_vector(conn, content_hash(path_body(PATH)), MODEL, unit(2))
    yield database
    database.close()


def _centroids(db: Database) -> dict[int, tuple[float, ...]]:
    with db.connect() as conn:
        return cluster_store.node_centroids(conn, TREE, MODEL)


def test_new_chunk_joins_best_centroid_and_untouched_stays(
    db: Database,
) -> None:
    with db.connect() as conn, conn:
        node_a, members_a = make_node(conn, topic=0, n=3)
        make_node(conn, topic=1, n=3)
        newcomer, _ = add_section(conn, b"a newcomer near topic 0\n", unit(0))
    centroids = _centroids(db)
    with db.connect() as conn, conn:
        report = placement.place(
            conn,
            TREE,
            [
                SectionDelta(
                    "new",
                    content_hash(b"a newcomer near topic 0\n"),
                    PATH,
                    section_id=newcomer,
                )
            ],
            centroids,
            MODEL,
            batch=1,
        )
    assert report.joined == 1
    with db.connect() as conn:
        assert cluster_store.section_node(conn, TREE, newcomer) == node_a
        # every original member of A is still in A: untouched never moves
        assert cluster_store.member_count(conn, node_a) == len(members_a) + 1


def test_new_chunk_below_tau_parks(db: Database) -> None:
    with db.connect() as conn, conn:
        make_node(conn, topic=0, n=3)
        make_node(conn, topic=1, n=3)
        orphan, digest = add_section(conn, b"unrelated topic\n", unit(3))
    centroids = _centroids(db)
    with db.connect() as conn, conn:
        report = placement.place(
            conn,
            TREE,
            [SectionDelta("new", digest, PATH, section_id=orphan)],
            centroids,
            MODEL,
            batch=1,
        )
    assert report.parked == 1
    with db.connect() as conn:
        assert cluster_store.section_node(conn, TREE, orphan) is None
        assert incubator.count(conn, TREE) == 1


def test_changed_chunk_sticky_stays_in_its_cluster(db: Database) -> None:
    with db.connect() as conn, conn:
        node_a, _ = make_node(conn, topic=0, n=3)
        make_node(conn, topic=1, n=3)
        # an edit whose content is still on topic 0
        edited, digest = add_section(
            conn, b"edit still about topic 0\n", unit(0)
        )
    centroids = _centroids(db)
    with db.connect() as conn, conn:
        report = placement.place(
            conn,
            TREE,
            [
                SectionDelta(
                    "changed",
                    digest,
                    PATH,
                    section_id=edited,
                    prior_node_id=node_a,
                )
            ],
            centroids,
            MODEL,
            batch=1,
        )
    assert report.stayed == 1 and report.joined == 0
    with db.connect() as conn:
        assert cluster_store.section_node(conn, TREE, edited) == node_a


def test_changed_chunk_off_topic_replaces_to_new_cluster(db: Database) -> None:
    with db.connect() as conn, conn:
        node_a, _ = make_node(conn, topic=0, n=3)
        node_b, _ = make_node(conn, topic=1, n=3)
        # was in A but its content now matches topic 1
        edited, digest = add_section(conn, b"edit now about topic 1\n", unit(1))
    centroids = _centroids(db)
    with db.connect() as conn, conn:
        report = placement.place(
            conn,
            TREE,
            [
                SectionDelta(
                    "changed",
                    digest,
                    PATH,
                    section_id=edited,
                    prior_node_id=node_a,
                )
            ],
            centroids,
            MODEL,
            batch=1,
        )
    assert report.stayed == 0 and report.joined == 1
    with db.connect() as conn:
        assert cluster_store.section_node(conn, TREE, edited) == node_b


def test_deleted_chunk_dissolves_cluster_below_two(db: Database) -> None:
    with db.connect() as conn, conn:
        make_node(conn, topic=0, n=3)
        node_b, members_b = make_node(conn, topic=1, n=3)
        node_c, members_c = make_node(conn, topic=1, n=2)
    centroids = _centroids(db)  # PRE-BATCH, before the delete
    gone_hash = None
    with db.connect() as conn, conn:
        # reconcile would have removed the deleted section; simulate that
        row = conn.execute(
            "SELECT content_hash FROM sections WHERE id = ?", (members_c[0],)
        ).fetchone()
        gone_hash = row["content_hash"]
        conn.execute("DELETE FROM sections WHERE id = ?", (members_c[0],))
        report = placement.place(
            conn,
            TREE,
            [SectionDelta("deleted", gone_hash, PATH, prior_node_id=node_c)],
            centroids,
            MODEL,
            batch=1,
        )
    assert report.deleted == 1 and report.dissolved == 1
    with db.connect() as conn:
        assert cluster_store.member_count(conn, node_c) == 0  # dissolved
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE id = ?", (node_c,)
            ).fetchone()[0]
            == 0
        )
        # the survivor (topic 1) re-placed into the remaining topic-1 cluster
        assert cluster_store.section_node(conn, TREE, members_c[1]) == node_b


def test_moved_chunk_reuses_content_and_stays(db: Database) -> None:
    with db.connect() as conn, conn:
        node_a, _ = make_node(conn, topic=0, n=3)
        moved, digest = add_section(conn, b"moved but same content\n", unit(0))
    centroids = _centroids(db)
    with db.connect() as conn, conn:
        report = placement.place(
            conn,
            TREE,
            [
                SectionDelta(
                    "moved",
                    digest,
                    PATH,
                    section_id=moved,
                    prior_node_id=node_a,
                )
            ],
            centroids,
            MODEL,
            batch=1,
        )
    assert report.stayed == 1
    with db.connect() as conn:
        assert cluster_store.section_node(conn, TREE, moved) == node_a


def test_a_parked_chunk_that_joins_is_unparked(db: Database) -> None:
    # the primitive's own guard: a join unparks, so a chunk cannot end up
    # clustered AND pending. No production caller reaches this today (both
    # routes park or re-place homeless chunks only), so pin it here.
    with db.connect() as conn, conn:
        node_a, _ = make_node(conn, topic=0, n=3)
        latecomer, digest = add_section(conn, b"near topic 0\n", unit(0))
        incubator.park(conn, TREE, latecomer, batch=1)
    centroids = _centroids(db)
    with db.connect() as conn, conn:
        outcome = placement.assign_or_park(
            conn,
            TREE,
            section_id=latecomer,
            content_hash=digest,
            path=PATH,
            centroids=centroids,
            model_name=MODEL,
            batch=2,
        )
    assert outcome == "joined"
    with db.connect() as conn:
        assert cluster_store.section_node(conn, TREE, latecomer) == node_a
        assert incubator.count(conn, TREE) == 0


def test_a_moved_section_is_re_attached_on_the_terms_it_had(
    db: Database,
) -> None:
    # the prior membership is the only record of how the section got there, and
    # reconcile has already dropped the row it lived on — so placement must
    # carry node, similarity AND the forced flag across a rename.
    with db.connect() as conn, conn:
        node_a, _ = make_node(conn, topic=0, n=3)
        make_node(conn, topic=1, n=3)
        # the renamed section's content is topic 1, i.e. NOT node A's topic:
        # only the carried membership can keep it where it belongs.
        moved, digest = add_section(conn, b"was forced into topic 0\n", unit(1))
    centroids = _centroids(db)
    with db.connect() as conn, conn:
        report = placement.place(
            conn,
            TREE,
            [
                SectionDelta(
                    "moved",
                    digest,
                    PATH,
                    section_id=moved,
                    prior_node_id=node_a,
                    prior_similarity=0.83,
                    prior_forced=True,
                )
            ],
            centroids,
            MODEL,
            batch=7,
        )
    assert report.stayed == 1
    with db.connect() as conn:
        member = cluster_store.membership(conn, TREE, moved)
        assert member is not None
        assert member.node_id == node_a
        assert member.similarity == 0.83
        assert member.forced is True
        assert incubator.count(conn, TREE) == 0


def test_a_moved_section_that_was_in_no_node_takes_the_placement_rule(
    db: Database,
) -> None:
    with db.connect() as conn, conn:
        make_node(conn, topic=0, n=3)
        homeless, digest = add_section(conn, b"unrelated topic\n", unit(3))
    centroids = _centroids(db)
    with db.connect() as conn, conn:
        report = placement.place(
            conn,
            TREE,
            [SectionDelta("moved", digest, PATH, section_id=homeless)],
            centroids,
            MODEL,
            batch=9,
        )
    assert report.parked == 1  # sub-TAU with nothing to preserve
    with db.connect() as conn:
        assert incubator.pending(conn, TREE)[0][3] == 9


def test_a_renamed_parked_section_keeps_its_original_batch(
    db: Database,
) -> None:
    with db.connect() as conn, conn:
        make_node(conn, topic=0, n=3)
        renamed, digest = add_section(conn, b"still unrelated\n", unit(3))
    centroids = _centroids(db)
    with db.connect() as conn, conn:
        placement.place(
            conn,
            TREE,
            [
                SectionDelta(
                    "moved",
                    digest,
                    PATH,
                    section_id=renamed,
                    prior_batch=2,  # the wait its predecessor had served
                )
            ],
            centroids,
            MODEL,
            batch=9,
        )
    with db.connect() as conn:
        assert incubator.pending(conn, TREE)[0][3] == 2
