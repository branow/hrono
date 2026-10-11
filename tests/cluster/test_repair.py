"""Local cluster repairs — split, migrate, dissolve."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono import pins
from hrono.cluster import incubator, monitor, repair
from hrono.cluster import store as cluster_store
from hrono.cluster.blend import path_body, register_path_bodies
from hrono.db.database import Database
from hrono.embed.store import upsert_vector
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content
from hrono.jobs.model import Job
from hrono.registry import store as registry_store
from tests.context import job_context

MODEL = "emb"
DIMS = 4
PATH = "src/x.py"
TREE = "default"


def unit(i: int) -> list[float]:
    v = [0.0] * DIMS
    v[i] = 1.0
    return v


def add_section(conn: object, body: bytes, vec: list[float]) -> int:
    digest = content_hash(body)
    upsert_content(conn, digest, body)  # type: ignore[arg-type]
    upsert_vector(conn, digest, MODEL, vec)  # type: ignore[arg-type]
    return insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "ex/repo", PATH, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )


def node_of(conn: object, sections: list[int]) -> int:
    return cluster_store.add_leaf_node(
        conn, TREE, [(s, False, None) for s in sections]
    )


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register_path_bodies(conn, [PATH])
        upsert_vector(conn, content_hash(path_body(PATH)), MODEL, unit(2))
        registry_store.insert(
            conn,
            "models",
            MODEL,
            '{"name":"emb","kind":"embedding","connection":null,'
            '"model":"fake","params":{"dims":4}}',
            None,
            "t",
        )
    yield database
    database.close()


def _job() -> Job:
    return Job(
        id="rep",
        parent_id=None,
        tree=TREE,
        op="repair",
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


def test_split_breaks_an_oversized_cluster_into_children(db: Database) -> None:
    # 32 members > MAX_CAP(30): 16 of topic 0, 16 of topic 1, in one node
    with db.connect() as conn, conn:
        sections = [
            add_section(conn, f"a{i}\n".encode(), unit(0)) for i in range(16)
        ]
        sections += [
            add_section(conn, f"b{i}\n".encode(), unit(1)) for i in range(16)
        ]
        big = node_of(conn, sections)

    def labeler(vectors: list[list[float]]) -> list[int]:
        return [0 if v[1] > 0.5 else 1 for v in vectors]  # split by topic

    with db.connect() as conn, conn:
        children = repair.split(conn, TREE, big, MODEL, core_labeler=labeler)
    assert len(children) == 2
    with db.connect() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE id = ?", (big,)
            ).fetchone()[0]
            == 0
        )  # oversized node retired
        for child in children:
            n = cluster_store.member_count(conn, child)
            assert 5 <= n <= 20
            # new nodes carry a content signature so a rebuild can match them
            sig = conn.execute(
                "SELECT signature FROM nodes WHERE id = ?", (child,)
            ).fetchone()["signature"]
            assert sig is not None


def test_split_leaves_a_within_cap_cluster_alone(db: Database) -> None:
    with db.connect() as conn, conn:
        small = node_of(
            conn,
            [add_section(conn, f"s{i}\n".encode(), unit(0)) for i in range(6)],
        )
    with db.connect() as conn, conn:
        assert repair.split(conn, TREE, small, MODEL) == ()
    with db.connect() as conn:
        assert cluster_store.member_count(conn, small) == 6


def test_split_re_anchors_a_pin_to_the_child_that_inherits_it(
    db: Database,
) -> None:
    """A divided topic is not a vanished one.

    `_restore_pinned` follows a dead anchor's surviving COMPANY to the node
    that inherited it — but a split moves the company into the children too,
    so there is nothing left to follow and the pin reads as spent. Here the
    successor is known exactly, so the pin is re-addressed at the moment it
    would otherwise be orphaned.
    """
    with db.connect() as conn, conn:
        left = [
            add_section(conn, f"p{i}\n".encode(), unit(0)) for i in range(16)
        ]
        right = [
            add_section(conn, f"q{i}\n".encode(), unit(1)) for i in range(16)
        ]
        big = node_of(conn, left + right)
        elsewhere = node_of(conn, [add_section(conn, b"other\n", unit(0))])
        held = left[0]
        pins.pin(
            conn, pins.MEMBERSHIP, held, reason="moved by hand", anchor=big
        )
        # a member of the SAME node whose pin names somewhere else: the split
        # is not entitled to re-address a decision about another topic, and
        # `_restore_pinned` will return this one to where it points.
        foreign = right[0]
        pins.pin(conn, pins.MEMBERSHIP, foreign, anchor=elsewhere)

    def labeler(vectors: list[list[float]]) -> list[int]:
        return [0 if v[1] > 0.5 else 1 for v in vectors]

    with db.connect() as conn, conn:
        children = repair.split(conn, TREE, big, MODEL, core_labeler=labeler)

    with db.connect() as conn:
        anchor = pins.anchors(conn, pins.MEMBERSHIP)[held]
        assert anchor in children
        assert held in {
            section
            for section, _h, _p in cluster_store.node_member_rows(conn, anchor)
        }
        # the operator's reason is theirs, and the split did not author it
        assert pins.reasons(conn, held)["membership"] == "moved by hand"
        assert pins.anchors(conn, pins.MEMBERSHIP)[foreign] == elsewhere


def test_split_refuses_a_cluster_that_yields_one_core(db: Database) -> None:
    # one core plus noise is not a division: attaching the noise to the single
    # core would rebuild the cluster that was already there, under a new id.
    with db.connect() as conn, conn:
        sections = [
            add_section(conn, f"c{i}\n".encode(), unit(0)) for i in range(32)
        ]
        big = node_of(conn, sections)

    def one_core(vectors: list[list[float]]) -> list[int]:
        return [-1 if i < 3 else 0 for i in range(len(vectors))]

    with db.connect() as conn, conn:
        assert repair.split(conn, TREE, big, MODEL, core_labeler=one_core) == ()
    with db.connect() as conn:
        assert cluster_store.member_count(conn, big) == 32


def test_migrate_moves_misfit_chunks_to_their_best_cluster(
    db: Database,
) -> None:
    with db.connect() as conn, conn:
        # A is mostly topic 0 but holds two topic-1 misfits
        a_members = [
            add_section(conn, f"a{i}\n".encode(), unit(0)) for i in range(4)
        ]
        strays = [
            add_section(conn, f"m{i}\n".encode(), unit(1)) for i in range(2)
        ]
        node_a = node_of(conn, a_members + strays)
        node_b = node_of(
            conn,
            [add_section(conn, f"b{i}\n".encode(), unit(1)) for i in range(4)],
        )
    with db.connect() as conn, conn:
        moved = repair.migrate(conn, TREE, node_a, MODEL)
    assert moved == 2
    with db.connect() as conn:
        for stray in strays:
            assert cluster_store.section_node(conn, TREE, stray) == node_b
        # the on-topic members stayed put
        for member in a_members:
            assert cluster_store.section_node(conn, TREE, member) == node_a


def test_dissolve_retires_a_below_two_cluster(db: Database) -> None:
    with db.connect() as conn, conn:
        node_of(
            conn,
            [add_section(conn, f"a{i}\n".encode(), unit(0)) for i in range(3)],
        )
        # a lone topic-0 member in its own node -> re-places into topic-0 node
        loner = add_section(conn, b"lone topic 0\n", unit(0))
        tiny = node_of(conn, [loner])
    with db.connect() as conn, conn:
        assert repair.dissolve(conn, TREE, tiny, MODEL, batch=1) is True
    with db.connect() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE id = ?", (tiny,)
            ).fetchone()[0]
            == 0
        )  # node retired
        assert (
            cluster_store.section_node(conn, TREE, loner) is not None
        )  # re-placed


def test_dissolve_parks_a_survivor_with_no_home(db: Database) -> None:
    with db.connect() as conn, conn:
        loner = add_section(conn, b"only topic 3\n", unit(3))
        tiny = node_of(
            conn, [loner]
        )  # the only cluster; nothing to re-place into
    with db.connect() as conn, conn:
        assert repair.dissolve(conn, TREE, tiny, MODEL, batch=1) is True
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 1  # parked


def _forced(conn: object, node_id: int, section_id: int) -> bool:
    return section_id in cluster_store.forced_members(conn, node_id)  # type: ignore[arg-type]


def test_a_forced_pioneer_leaves_once_its_real_siblings_form(
    db: Database,
) -> None:
    # `docs/unrelated-cooking-notes.md` force-assigned at 0.281 into a
    # source-code topic. One alien member in seven is a rate of 0.14 — under
    # MISFIT_THRESHOLD — so the rate alone never triggers the repair that frees
    # it. The flag does.
    with db.connect() as conn, conn:
        members = [
            add_section(conn, f"code{i}\n".encode(), unit(0)) for i in range(6)
        ]
        pioneer = add_section(conn, b"cooking notes\n", unit(3))
        married = cluster_store.add_leaf_node(
            conn,
            TREE,
            [(s, False, None) for s in members] + [(pioneer, True, 0.281)],
        )
        siblings = [  # its real siblings finally form a cluster of their own
            add_section(conn, f"cooking{i}\n".encode(), unit(3))
            for i in range(3)
        ]
        home = node_of(conn, siblings)
        monitor.refresh(conn, TREE, MODEL, [married, home])

    with db.connect() as conn:
        assert monitor.cluster_rate(conn, TREE, married) < (
            repair.MISFIT_THRESHOLD
        )

    with db.connect() as conn, conn:
        repair.repair(_job(), job_context(db, Path(".")))

    with db.connect() as conn:
        assert cluster_store.section_node(conn, TREE, pioneer) == home
        assert not _forced(conn, home, pioneer)  # re-placed normally: flag gone


def test_a_forced_member_with_nowhere_better_stays_put(db: Database) -> None:
    # the repair must not shuffle a pioneer into a cluster that fits it worse
    # just because it is flagged: with no better home it keeps its place, and
    # keeps its flag, so the next batch looks again.
    with db.connect() as conn, conn:
        members = [
            add_section(conn, f"code{i}\n".encode(), unit(0)) for i in range(6)
        ]
        pioneer = add_section(conn, b"cooking notes\n", unit(3))
        married = cluster_store.add_leaf_node(
            conn,
            TREE,
            [(s, False, None) for s in members] + [(pioneer, True, 0.281)],
        )
        node_of(conn, [add_section(conn, b"other\n", unit(1))])
        monitor.refresh(conn, TREE, MODEL, [married])

    with db.connect() as conn, conn:
        repair.repair(_job(), job_context(db, Path(".")))

    with db.connect() as conn:
        assert cluster_store.section_node(conn, TREE, pioneer) == married
        assert _forced(conn, married, pioneer)


def test_repair_reports_what_it_did(db: Database) -> None:
    # "succeeded" does not say whether a cluster was dissolved, a pioneer
    # freed, or nothing needed doing at all.
    with db.connect() as conn, conn:
        members = [
            add_section(conn, f"code{i}\n".encode(), unit(0)) for i in range(6)
        ]
        node_of(conn, members)
        lonely = node_of(conn, [add_section(conn, b"alone\n", unit(1))])

    outcome = repair.repair(_job(), job_context(db, Path(".")))

    assert set(outcome) == {
        "dissolved",
        "split",
        "migrated",
        "freed",
        "reparented",
        "pinned",
        "removed",
    }
    assert outcome["dissolved"] == 1  # the below-two cluster
    assert lonely not in [int(r["id"]) for r in _nodes(db)]


def _nodes(db: Database):
    with db.connect() as conn:
        return conn.execute("SELECT id FROM nodes").fetchall()


def test_freed_counts_pioneers_not_migrations(db: Database) -> None:
    # `freed` is the headline number — a force-assigned pioneer released.
    # It must be able to DISAGREE with `migrated`, or it is just a second name
    # for the same count and an operator reading "freed: 7" would believe seven
    # alien members were revisited when the true number is one.
    with db.connect() as conn, conn:
        members = [
            add_section(conn, f"code{i}\n".encode(), unit(0)) for i in range(4)
        ]
        pioneer = add_section(conn, b"cooking notes\n", unit(3))
        strays = [  # ordinary misfits: nearer another cluster, NOT forced
            add_section(conn, f"cooking-stray{i}\n".encode(), unit(3))
            for i in range(2)
        ]
        married = cluster_store.add_leaf_node(
            conn,
            TREE,
            [(s, False, None) for s in members]
            + [(pioneer, True, 0.281)]
            + [(s, False, None) for s in strays],
        )
        home = node_of(
            conn,
            [
                add_section(conn, f"cooking{i}\n".encode(), unit(3))
                for i in range(3)
            ],
        )
        monitor.refresh(conn, TREE, MODEL, [married, home])

    outcome = repair.repair(_job(), job_context(db, Path(".")))

    assert outcome["migrated"] > outcome["freed"]  # they really do disagree
    assert outcome["freed"] == 1  # exactly the one that was forced


def test_a_split_leaves_both_halves_WHERE_THE_TOPIC_WAS(db: Database) -> None:
    """The halves must be attached where the original was: otherwise a topic
    under the root becomes two nodes beside the tree. On the map: two circles
    with no line to anything, and a root whose brief silently stops covering
    part of the corpus."""
    with db.connect() as conn, conn:
        sections = [
            add_section(conn, f"a{i}\n".encode(), unit(0)) for i in range(16)
        ]
        sections += [
            add_section(conn, f"b{i}\n".encode(), unit(1)) for i in range(16)
        ]
        big = node_of(conn, sections)
        above = int(
            conn.execute(
                "INSERT INTO nodes(tree, level, label, created_at) "
                "VALUES (?, 1, 7, datetime('now')) RETURNING id",
                (TREE,),
            ).fetchone()["id"]
        )
        cluster_store.add_child(
            conn, above, big, attached=True, similarity=None
        )

    def labeler(vectors: list[list[float]]) -> list[int]:
        return [0 if v[1] > 0.5 else 1 for v in vectors]

    with db.connect() as conn, conn:
        children = repair.split(conn, TREE, big, MODEL, core_labeler=labeler)

    with db.connect() as conn:
        assert len(children) == 2
        for child in children:
            assert cluster_store.parent_of(conn, child) == above
        # and the retired topic is not still hanging there beside them
        assert cluster_store.parent_of(conn, big) is None


def test_an_emptied_leaf_is_dissolved_even_with_no_centroid(
    db: Database,
) -> None:
    """A leaf whose members are gone must not keep serving its brief.

    The op must not iterate ``node_centroids``, which skips a node with no
    vectors — a leaf emptied by a cascade or a migration would be invisible to
    the one repair (dissolve) it needs, and its brief and node:// passages
    would keep answering recall for ever.
    """
    with db.connect() as conn, conn:
        a = add_section(conn, b"alpha body", unit(0))
        b = add_section(conn, b"beta body", unit(0))
        node_of(conn, [a, b])  # a healthy neighbour the sweep must keep
        ghost = cluster_store.add_leaf_node(conn, TREE, [])

    repair.repair(_job(), job_context(db, Path(".")))

    with db.connect() as conn:
        gone = conn.execute(
            "SELECT 1 FROM nodes WHERE id = ?", (ghost,)
        ).fetchone()
        kept = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE tree = ?", (TREE,)
        ).fetchone()[0]
    assert gone is None
    assert kept == 1


def test_a_childless_upper_node_is_removed(db: Database) -> None:
    # a parent that lost every child kept its stale brief: `brief_upper`
    # skips a node with no child briefs, so nothing ever rewrote OR removed
    # it, and export and recall kept serving text about children that no
    # longer exist.
    with db.connect() as conn, conn:
        a = add_section(conn, b"alpha body", unit(0))
        b = add_section(conn, b"beta body", unit(0))
        node_of(conn, [a, b])
        hollow = int(
            conn.execute(
                "INSERT INTO nodes(tree, level, label, created_at) "
                "VALUES (?, 1, 0, 't')",
                (TREE,),
            ).lastrowid
        )

    outcome = repair.repair(_job(), job_context(db, Path(".")))

    with db.connect() as conn:
        gone = conn.execute(
            "SELECT 1 FROM nodes WHERE id = ?", (hollow,)
        ).fetchone()
    assert gone is None
    assert outcome["removed"] == 1


def test_a_dissolve_spares_a_leaf_holding_a_pinned_member(
    db: Database,
) -> None:
    # a one-member topic a human pinned a chunk into is the operator's
    # decision, and dissolving it re-places the chunk by machine judgement —
    # the revert pins exist to prevent.
    with db.connect() as conn, conn:
        a = add_section(conn, b"alpha body", unit(0))
        b = add_section(conn, b"beta body", unit(0))
        node_of(conn, [a, b])
        held = add_section(conn, b"hand placed", unit(1))
        topic = node_of(conn, [held])
        pins.pin(conn, pins.MEMBERSHIP, held, reason="hand", anchor=topic)

    repair.repair(_job(), job_context(db, Path(".")))

    with db.connect() as conn:
        kept = conn.execute(
            "SELECT 1 FROM nodes WHERE id = ?", (topic,)
        ).fetchone()
    assert kept is not None


def test_split_deals_a_vectorless_member_into_the_biggest_child(
    db: Database,
) -> None:
    # a member with no vector cannot be judged by the cores, but dropping it
    # would break the pool invariant: it would end up in no cluster and not
    # pending.
    with db.connect() as conn, conn:
        left = [
            add_section(conn, f"left {i}".encode(), unit(0)) for i in range(4)
        ]
        right = [
            add_section(conn, f"right {i}".encode(), unit(1)) for i in range(2)
        ]
        blind = insert_section(
            conn,
            source="repo",
            address=Address("git", "ex/repo", PATH, "v1"),
            start=0,
            end=5,
            content_hash=_store_unvectored(conn, b"no vector here"),
            ordinal=9,
        )
        node = node_of(conn, [*left, *right, blind])

    with db.connect() as conn, conn:
        halves = repair.split(
            conn,
            TREE,
            node,
            MODEL,
            core_labeler=lambda vecs: [
                0 if v[0] > 0 else 1 for v in list(vecs)
            ],
            over=5,
        )

    assert len(halves) == 2
    with db.connect() as conn:
        home = conn.execute(
            "SELECT node_id, forced FROM node_members WHERE section_id = ?",
            (blind,),
        ).fetchone()
        sizes = {
            h: int(
                conn.execute(
                    "SELECT COUNT(*) FROM node_members WHERE node_id = ?",
                    (h,),
                ).fetchone()[0]
            )
            for h in halves
        }
    assert home is not None  # the chunk is still in exactly one cluster
    assert int(home["node_id"]) == max(sizes, key=lambda h: sizes[h])
    assert int(home["forced"]) == 1  # flagged for the monitor to revisit


def _store_unvectored(conn: object, body: bytes) -> str:
    digest = content_hash(body)
    upsert_content(conn, digest, body)  # type: ignore[arg-type]
    return digest
