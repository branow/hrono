"""Settle — churn/misfit trigger + warm reconcile near-no-op."""

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono import pins
from hrono.cluster import monitor, repair
from hrono.cluster import store as cluster_store
from hrono.cluster.blend import register_path_bodies
from hrono.cluster.build import ClusterResult
from hrono.cluster.incubator import count as incubator_count
from hrono.cluster.incubator import park
from hrono.cluster.recipe import MIN_POINTS
from hrono.db.database import Database
from hrono.embed.model import resolve_embedding_model
from hrono.export import store as export_store
from hrono.export.collapse import collapse
from hrono.export.render import render
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.registry import store as registry_store
from hrono.summarize import store as condensations
from hrono.tree import settle as settle_mod
from hrono.tree.maintain import maintain
from hrono.tree.settle import CHURN_THRESHOLD, settle, should_settle
from tests import world
from tests.cluster.harness import planted_groups
from tests.cluster.invariant import (
    assert_every_leaf_is_reachable,
    assert_pool_invariant,
)
from tests.context import job_context

DIMS = 8
TREE = "default"


class FakeCompletion:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        return CompletionResult(
            "This topic covers the module's API and how its parts fit.",
            Usage(10, 4),
        )


def fake_encoder(model_id: str):
    def encode(texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * (DIMS - 1) for _ in texts]

    return encode


def fake_build(vectors: object, *, init: object = None) -> ClusterResult:
    n = len(vectors)  # type: ignore[arg-type]
    return ClusterResult(
        labels=tuple(i // 3 for i in range(n)),
        attached=tuple(False for _ in range(n)),
        assignment_similarity=tuple(None for _ in range(n)),
        coords=tuple((0.0,) for _ in range(n)),
    )


def make_repo(path: Path) -> str:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "t@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"], check=True
    )
    for i in range(9):
        (path / f"f{i}.txt").write_text(f"module {i} does thing {i}\n")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "one"], check=True)
    return path.as_uri()


def register(conn: object, url: str) -> None:
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "sources",
        "repo",
        json.dumps({"name": "repo", "type": "git", "url": url, "auth": {}}),
        None,
        "t",
    )
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "models",
        "emb",
        json.dumps(
            {
                "name": "emb",
                "kind": "embedding",
                "connection": None,
                "model": "fake",
                "params": {"dims": DIMS, "batch_size": 8},
            }
        ),
        None,
        "t",
    )
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "models",
        "sonnet",
        json.dumps(
            {
                "name": "sonnet",
                "kind": "text",
                "connection": "c",
                "model": "claude",
                "params": {},
            }
        ),
        None,
        "t",
    )
    for role in ("condense", "brief", "brief-upper"):
        registry_store.insert(
            conn,  # type: ignore[arg-type]
            "prompts",
            role,
            json.dumps({"name": role, "role": role, "template": "X {content}"}),
            None,
            "t",
        )


def _job() -> Job:
    return Job(
        id="s",
        parent_id=None,
        tree=TREE,
        op="settle",
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture(scope="module")
def _world(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """The tree `maintain` builds over a repo, built once."""
    root = tmp_path_factory.mktemp("world")
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(root)
        url = make_repo(root / "src-repo")
        database = Database.at(root / "hrono.db")
        with database.connect() as conn, conn:
            register(conn, url)
        maintain(
            Job(
                id="m",
                parent_id=None,
                tree=TREE,
                op="maintain",
                scope={},
                status="running",
                error=None,
                created_at="t",
                updated_at="t",
            ),
            job_context(database, root),
            encoder_for=fake_encoder,
            client=FakeCompletion(),
            build=fake_build,
        )
        database.close()
    return root, world.snapshot(root, tmp_path_factory.mktemp("copy"))


@pytest.fixture
def tmp_path(_world: tuple[Path, Path]) -> Path:
    """Shadows pytest's: every test here starts in the built world."""
    root, copy = _world
    return world.restore(copy, root)


@pytest.fixture
def built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Database]:
    monkeypatch.chdir(tmp_path)
    database = Database.at(tmp_path / "hrono.db")
    yield database
    database.close()


def _set_drift(db: Database, drift: int) -> None:
    with db.connect() as conn, conn:
        conn.execute(
            "INSERT INTO tree_batch(tree, batch, drift) VALUES (?, 0, ?) "
            "ON CONFLICT(tree) DO UPDATE SET drift = excluded.drift",
            (TREE, drift),
        )


def _drift(db: Database) -> int:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT drift FROM tree_batch WHERE tree = ?", (TREE,)
        ).fetchone()
        return int(row["drift"]) if row else 0


def _node_ids(db: Database) -> list[int]:
    with db.connect() as conn:
        return sorted(
            int(r["id"]) for r in conn.execute("SELECT id FROM nodes")
        )


def test_registered() -> None:
    assert "settle" in OPS


def test_churn_threshold_triggers(built: Database) -> None:
    with built.connect() as conn:
        assert should_settle(conn, TREE) is False  # fresh, no drift
    _set_drift(built, CHURN_THRESHOLD)
    with built.connect() as conn:
        assert should_settle(conn, TREE) is True


def test_misfit_backstop_triggers(built: Database) -> None:
    with built.connect() as conn, conn:
        # baseline low, current global misfit high -> backstop trips
        monitor.capture_baseline(conn, TREE, 0.01)
        conn.execute(
            "INSERT INTO misfit(tree, node_id, misfits, members, updated_at) "
            "SELECT ?, id, 1, 1, 't' FROM nodes WHERE tree = ? AND level = 0",
            (TREE, TREE),
        )
    with built.connect() as conn:
        assert monitor.global_rate(conn, TREE) > 2 * 0.01
        assert should_settle(conn, TREE) is True


def test_settle_over_unchanged_corpus_is_near_no_op(
    built: Database, tmp_path: Path
) -> None:
    ids_before = _node_ids(built)
    counter = FakeCompletion()
    settle(
        _job(),
        job_context(built, tmp_path),
        force=True,
        build=fake_build,
        encoder_for=fake_encoder,
        client=counter,
    )
    # warm rebuild reproduces the layout: ids are stable, brief freshness
    # skips every brief
    assert counter.calls == 0
    assert _node_ids(built) == ids_before


def test_settle_resets_the_churn_counter(
    built: Database, tmp_path: Path
) -> None:
    _set_drift(built, CHURN_THRESHOLD + 5)
    settle(
        _job(),
        job_context(built, tmp_path),
        build=fake_build,
        encoder_for=fake_encoder,
        client=FakeCompletion(),
    )
    assert _drift(built) == 0


def test_untriggered_settle_leaves_the_counter(
    built: Database, tmp_path: Path
) -> None:
    _set_drift(built, 3)  # below threshold, no misfit backstop
    settle_mod.settle(
        _job(),
        job_context(built, tmp_path),
        build=fake_build,
        encoder_for=fake_encoder,
        client=FakeCompletion(),
    )
    assert _drift(built) == 3  # never ran, counter untouched


def _park_a_member(db: Database) -> int:
    """Park a chunk that a rebuild will home: both parked and a member."""
    with db.connect() as conn, conn:
        row = conn.execute(
            "SELECT section_id FROM node_members LIMIT 1"
        ).fetchone()
        park(conn, TREE, int(row["section_id"]), batch=1)
    return int(row["section_id"])


def test_settle_retires_a_pool_row_its_rebuild_has_re_homed(
    built: Database,
    tmp_path: Path,
) -> None:
    section_id = _park_a_member(built)
    with built.connect() as conn:
        assert incubator_count(conn, TREE) == 1
    settle(
        _job(),
        job_context(built, tmp_path),
        force=True,
        build=fake_build,
        encoder_for=fake_encoder,
        client=FakeCompletion(),
    )
    with built.connect() as conn:
        assert incubator_count(conn, TREE) == 0, section_id
    assert_pool_invariant(built, TREE, "emb")


def _park_unembedded(db: Database, count: int) -> None:
    """Park chunks the rebuild cannot see — they embed only later in settle."""
    path = "late/arrivals.txt"
    with db.connect() as conn, conn:
        register_path_bodies(conn, [path])
        for i in range(count):
            body = f"late arrival {i}\n".encode()
            digest = content_hash(body)
            upsert_content(conn, digest, body)
            section_id = insert_section(
                conn,
                source="repo",
                address=Address("git", "ex/repo", path, "v1"),
                start=0,
                end=len(body),
                content_hash=digest,
                ordinal=0,
            )
            park(conn, TREE, section_id, batch=1)
            condensations.upsert(conn, digest, "sonnet", "a plain gist.", 1, 1)


def test_settle_drains_chunks_its_own_embed_pass_made_placeable(
    built: Database,
    tmp_path: Path,
) -> None:
    # cluster runs before embed, so a chunk with no vector yet is invisible to
    # the rebuild; settle's closing drain is what re-homes it.
    _park_unembedded(built, MIN_POINTS)
    settle(
        _job(),
        job_context(built, tmp_path),
        force=True,
        build=fake_build,
        encoder_for=fake_encoder,
        client=FakeCompletion(),
    )
    with built.connect() as conn:
        assert incubator_count(conn, TREE) == 0
    assert_pool_invariant(built, TREE, "emb")


def _leaf_ids(db: Database) -> list[int]:
    with db.connect() as conn:
        return [
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM nodes WHERE tree = ? AND level = 0", (TREE,)
            ).fetchall()
        ]


def _briefed(db: Database) -> set[int]:
    with db.connect() as conn:
        return {
            int(row["node_id"])
            for row in conn.execute("SELECT node_id FROM briefs").fetchall()
        }


def planted_encoder(model_id: str):
    """Give the parked late arrivals their own density core, everything else
    the flat corpus direction."""
    vectors, _ = planted_groups(
        groups=2, per_group=7, dim=DIMS - 1, spread=0.1, noise=0, seed=1
    )

    def encode(texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            if text.startswith("late arrival "):
                index = int(text.split()[2])
                out.append([0.0] + [float(v) for v in vectors[index]])
            else:
                out.append([1.0] + [0.0] * (DIMS - 1))
        return out

    return encode


def test_a_leaf_node_the_settle_drain_emits_is_briefed_and_reachable(
    built: Database,
    tmp_path: Path,
) -> None:
    # the drain runs BEFORE the brief pass, so a leaf it emits is summarised
    # in the same settle; attach-by-proximity then gives it its nearest
    # parent, because root.md's children are rendered from parent EDGES —
    # without one the topic is written to the export and unreachable in it.
    # Pinned so settle's docstring and the code cannot drift apart.
    before = _leaf_ids(built)
    _park_unembedded(built, 14)
    settle(
        _job(),
        job_context(built, tmp_path),
        force=True,
        build=fake_build,
        encoder_for=planted_encoder,
        client=FakeCompletion(),
    )
    emitted = set(_leaf_ids(built)) - set(before)
    assert emitted  # the drain reduced the pool into real clusters
    assert emitted <= _briefed(built)
    assert emitted <= _parented(built)  # an edge, so root.md links it

    files = _export(built)
    for node_id in emitted:
        directory = next(
            p.rsplit("/", 1)[0]
            for p in files
            if p.endswith(f"-{node_id}/brief.md")
        )
        assert f"{directory}/brief.md" in files
        assert directory in files["root.md"]  # reachable by walking the map
    assert_pool_invariant(built, TREE, "emb")
    assert_every_leaf_is_reachable(built, TREE)


def _export(db: Database) -> dict[str, str]:
    with db.connect() as conn:
        stored = export_store.load(conn, TREE)
        assert stored is not None
        return render(conn, collapse(stored, 3))


def _parented(db: Database) -> set[int]:
    with db.connect() as conn:
        return {
            int(row["child_id"])
            for row in conn.execute(
                "SELECT child_id FROM node_children"
            ).fetchall()
        }


def _members(database: Database) -> dict[int, int]:
    with database.connect() as conn:
        return {
            int(r["section_id"]): int(r["node_id"])
            for r in conn.execute(
                "SELECT section_id, node_id FROM node_members"
            ).fetchall()
        }


def test_settle_returns_a_pinned_member_to_its_anchor(
    built: Database, tmp_path: Path
) -> None:
    """The rebuild rewrites every membership, so the pin restores it.

    `settle` re-clusters the whole leaf level — `replace_tree` writes every
    `node_members` row fresh — so honouring a pin here cannot mean "do not
    move it". It means putting it back before anything reads the new map, and
    `brief` reads membership two steps later.
    """
    placed = _members(built)
    section, home = next(iter(placed.items()))
    elsewhere = next(
        (node for sec, node in placed.items() if node != home), None
    )
    if elsewhere is None:  # a one-topic corpus cannot show the property
        pytest.skip("the built corpus has a single topic")

    company = {sec for sec, node in placed.items() if node == elsewhere}
    with built.write() as conn:
        # a human moved it, then pinned it there
        conn.execute(
            "DELETE FROM node_members WHERE section_id = ?", (section,)
        )
        cluster_store.add_member(
            conn, elsewhere, section, forced=False, similarity=None
        )
        pins.pin(conn, pins.MEMBERSHIP, section, anchor=elsewhere)

    outcome = settle(
        _job(),
        job_context(built, tmp_path),
        force=True,
        build=fake_build,
        encoder_for=fake_encoder,
        client=FakeCompletion(),
    )

    # assert the PROPERTY, not the id: the hand-move changed the anchor's
    # content, so the content-signature id reuse may retire that node and
    # give the topic a new id. What must hold is that the chunk is still with
    # the neighbours the operator put it among, and did not drift back to
    # where it came from.
    after = _members(built)
    landed = after[section]
    assert {sec for sec, node in after.items() if node == landed} >= company
    assert landed != home
    assert outcome["held"] == 1
    assert outcome["released"] == 0


def test_a_pin_survives_a_hand_split_of_the_topic_it_names(
    built: Database, tmp_path: Path
) -> None:
    """A membership pin survives a hand split of its anchor, end to end.

    A split retires the anchor AND scatters the company `_restore_pinned`
    would otherwise follow, so without the re-anchor this settle would report
    the pin RELEASED — the operator's correction dropped by their own later
    division of the same topic.
    """
    placed = _members(built)
    section, home = next(iter(placed.items()))
    if sum(1 for node in placed.values() if node == home) < 2:
        pytest.skip("a one-member topic cannot be split")
    with built.write() as conn:
        pins.pin(
            conn, pins.MEMBERSHIP, section, reason="moved by hand", anchor=home
        )
        model = str(resolve_embedding_model(conn, {})["name"])
        # the seam, because the subject here is the PIN and not the recipe:
        # the built corpus is smaller than the clustering floor, and the
        # server's split tests already drive the real UMAP -> HDBSCAN split.
        children = repair.split(
            conn,
            TREE,
            home,
            model,
            over=0,
            core_labeler=lambda vectors: [i % 2 for i in range(len(vectors))],
        )
    if len(children) < 2:
        pytest.skip("the built corpus has an indivisible topic")

    outcome = settle(
        _job(),
        job_context(built, tmp_path),
        force=True,
        build=fake_build,
        encoder_for=fake_encoder,
        client=FakeCompletion(),
    )

    assert outcome["released"] == 0
    assert outcome["held"] == 1
    with built.connect() as conn:
        assert pins.is_pinned(conn, pins.MEMBERSHIP, section) is True


def test_a_pin_whose_anchor_is_gone_is_released_not_guessed(
    built: Database, tmp_path: Path
) -> None:
    # the topic a human chose no longer exists. Parking the chunk in whichever
    # cluster inherited its neighbours would be a worse answer than admitting
    # the pin is spent, and it would be invisible.
    placed = _members(built)
    section = next(iter(placed))
    with built.write() as conn:
        pins.pin(conn, pins.MEMBERSHIP, section, anchor=999_999)

    outcome = settle(
        _job(),
        job_context(built, tmp_path),
        force=True,
        build=fake_build,
        encoder_for=fake_encoder,
        client=FakeCompletion(),
    )

    assert outcome["released"] == 1
    with built.connect() as conn:
        assert pins.is_pinned(conn, pins.MEMBERSHIP, section) is False


def test_an_untriggered_settle_reports_that_it_did_nothing(
    built: Database, tmp_path: Path
) -> None:
    outcome = settle_mod.settle(
        _job(),
        job_context(built, tmp_path),
        build=fake_build,
        encoder_for=fake_encoder,
        client=FakeCompletion(),
    )

    assert outcome == {"settled": False, "held": 0, "released": 0}


def test_settle_leaves_another_tree_s_pins_and_membership_alone(
    built: Database, tmp_path: Path
) -> None:
    """Pins and memberships are GLOBAL rows; settle must act on its tree's.

    Before the scope fix, this tree's settle read every membership pin, found
    the other tree's anchor absent from its own live set, and RELEASED the pin
    a human placed in a tree this run had no business touching.
    """
    with built.connect() as conn, conn:
        other_node = int(
            conn.execute(
                "INSERT INTO nodes(tree, level, label, created_at) "
                "VALUES ('other', 0, 0, 't')"
            ).lastrowid
        )
        body = b"a chunk that lives in the other tree"
        digest = content_hash(body)
        upsert_content(conn, digest, body)
        section = insert_section(
            conn,
            source="other-src",
            address=Address("git", "x", "a.txt", "v"),
            start=0,
            end=len(body),
            content_hash=digest,
            ordinal=0,
        )
        cluster_store.add_member(
            conn, other_node, section, forced=False, similarity=None
        )
        pins.pin(
            conn, pins.MEMBERSHIP, section, reason="hand", anchor=other_node
        )

    settle(
        _job(),
        job_context(built, tmp_path),
        force=True,
        build=fake_build,
        encoder_for=fake_encoder,
        client=FakeCompletion(),
    )

    with built.connect() as conn:
        held = pins.held_for(conn, pins.MEMBERSHIP, [section])
        member = conn.execute(
            "SELECT node_id FROM node_members WHERE section_id = ?",
            (section,),
        ).fetchone()
    assert held == {section: (other_node, "hand")}
    assert member is not None and int(member["node_id"]) == other_node
