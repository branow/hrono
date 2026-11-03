"""One op brings a tree up to date, in the order the stages require."""

import itertools
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono import pins
from hrono.cluster import store as cluster_store
from hrono.cluster.monitor import monitor
from hrono.db.database import Database
from hrono.ingest.identity import content_hash
from hrono.jobs.model import Job
from hrono.jobs.stages import StageFailed
from hrono.llm.client import (
    CompletionRequest,
    CompletionResult,
    LLMError,
    Usage,
)
from hrono.registry import store as registry_store
from hrono.summarize import review
from hrono.tree import sync_chain
from hrono.tree.maintain import maintain
from hrono.tree.sync_chain import sync
from tests import world
from tests.context import job_context
from tests.tree.test_update import (
    edit,
    fake_build,
    fake_encoder,
    make_repo,
    register,
)

TREE = "default"


class Judge:
    """A completion that tells a judge prompt from a brief prompt.

    Brief replies are NUMBERED on purpose: a regenerated brief must be
    distinguishable from one that was left alone, and a fake that always
    returns the same sentence makes "did this stage run?" unanswerable.
    """

    def __init__(self, verdict: str = "major") -> None:
        self.verdict = verdict
        self.calls = 0
        self.briefs = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        if "S " in request.content and " M " in request.content:
            return CompletionResult(self.verdict, Usage(1, 1))
        self.briefs += 1
        return CompletionResult(
            f"This topic covers the module's API, revision {self.briefs}.",
            Usage(10, 4),
        )


def _job(op: str) -> Job:
    return Job(
        id=op,
        parent_id=None,
        tree=TREE,
        op=op,
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture(scope="module")
def _world(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """The tree `maintain` builds over the repo, built once."""
    root = tmp_path_factory.mktemp("world")
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(root)
        url = make_repo(root / "src-repo")
        database = Database.at(root / "hrono.db")
        with database.connect() as conn, conn:
            register(conn, url)
            registry_store.insert(
                conn,
                "prompts",
                "judge",
                json.dumps(
                    {
                        "name": "judge",
                        "role": "judge",
                        "template": "S {source} M {summary}",
                    }
                ),
                None,
                "t",
            )
        maintain(
            _job("maintain"),
            job_context(database, root),
            encoder_for=fake_encoder,
            client=Judge(),
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
) -> Iterator[tuple[Database, Path]]:
    monkeypatch.chdir(tmp_path)
    database = Database.at(tmp_path / "hrono.db")
    yield database, tmp_path / "src-repo"
    database.close()


def _uncondensed(db: Database) -> int:
    with db.connect() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM node_members m "
                "JOIN sections s ON s.id = m.section_id "
                "WHERE NOT EXISTS (SELECT 1 FROM condensations d "
                "                  WHERE d.content_hash = s.content_hash)"
            ).fetchone()[0]
        )


def _run(db: Database, tmp_path: Path, client: object) -> object:
    return sync(
        _job("sync-tree"),
        job_context(db, tmp_path),
        encoder_for=fake_encoder,
        client=client,
        core_labeler=lambda vectors: [0] * len(vectors),
    )


def test_a_changed_file_leaves_the_tree_up_to_date(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # the whole point: after ONE command the map reflects the new code.
    db, origin = built
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")

    before = _upper_briefs(db)
    leaves_before = _leaf_briefs(db)

    _run(db, tmp_path, Judge())

    after = _upper_briefs(db)
    assert _uncondensed(db) == 0  # nothing unsummarised
    # propagate MARKS ONLY — it is brief-upper that repairs what it marked. If
    # that stage never runs the chain leaves ancestors known to be wrong,
    # flagged as wrong, and still serving their old text.
    assert after != before  # an ancestor's brief was actually regenerated
    assert all(row["stale"] == 0 for row in after.values())  # marks cleared
    with db.connect() as conn:
        measured = conn.execute(
            "SELECT COUNT(*) FROM misfit WHERE tree = ?", (TREE,)
        ).fetchone()[0]
    assert measured > 0  # monitor ran and stored what it measured
    # and the changed leaf itself was re-briefed, not only its ancestors
    assert _leaf_briefs(db) != leaves_before


def test_the_result_says_what_the_run_did(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # one verb over six stages is a black box unless it reports.
    db, origin = built
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")

    outcome = _run(db, tmp_path, Judge())

    # every stage that makes a judgement contributes its counts
    assert set(outcome) == {
        "changed",
        "forced",
        "parked",
        "judged",
        "propagated",
        "skipped",
        "abstained",
        "misfit_rate",
        "above_baseline",
        "repaired",
        # what the stages AFTER repair put back: a split retires a topic and
        # makes two in its place, and unless the run briefs and re-parents
        # them they are left beside the tree, under no root
        "adopted",
        "settle_due",
        "incomplete",
        # what the run did to the map, and each stage with its time
        "tree",
        "stages",
    }
    assert [stage["op"] for stage in outcome["stages"]] == [
        "update",
        "propagate",
        "brief",
        "brief-upper",
        "embed",  # condensations and briefs, so monitor measures the new space
        "monitor",
        "repair",
        "adopt",
        "embed",
        "health",
    ]
    assert all(stage["seconds"] >= 0 for stage in outcome["stages"])
    assert outcome["incomplete"] is False
    assert outcome["changed"] is True  # a file really did change
    assert set(outcome["repaired"]) == {
        "dissolved",
        "split",
        "migrated",
        "freed",
        "reparented",
        "pinned",
        "removed",
    }


def test_settle_is_reported_never_run(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # hrono does not spend money unasked: the churn trigger INFORMS.
    db, origin = built
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    with db.connect() as conn, conn:  # force the trigger well past threshold
        conn.execute(
            "INSERT INTO tree_batch(tree, batch, drift) VALUES (?, 0, 9999) "
            "ON CONFLICT(tree) DO UPDATE SET drift = 9999",
            (TREE,),
        )
    before = _node_ids(db)

    outcome = _run(db, tmp_path, Judge())

    assert outcome["settle_due"] is True  # the trigger fired ...
    assert _node_ids(db) == before  # ... and nothing re-clustered on its own


def _leaf_briefs(db: Database) -> dict[int, str]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT b.node_id AS id, b.text AS text FROM briefs b "
            "JOIN nodes n ON n.id = b.node_id "
            "WHERE n.tree = ? AND n.level = 0",
            (TREE,),
        ).fetchall()
    return {int(r["id"]): str(r["text"]) for r in rows}


def _upper_briefs(db: Database) -> dict[int, dict[str, object]]:
    """Each non-leaf brief's text and stale flag, to compare across a run."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT b.node_id AS id, b.text AS text, b.stale AS stale, "
            "b.member_signature AS sig FROM briefs b "
            "JOIN nodes n ON n.id = b.node_id "
            "WHERE n.tree = ? AND n.level > 0",
            (TREE,),
        ).fetchall()
    return {
        int(r["id"]): {"text": r["text"], "stale": r["stale"], "sig": r["sig"]}
        for r in rows
    }


def _node_ids(db: Database) -> list[int]:
    with db.connect() as conn:
        return sorted(
            int(r["id"]) for r in conn.execute("SELECT id FROM nodes")
        )


def test_a_failing_stage_names_itself_and_leaves_the_rest_committed(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # a stage that raises must fail the job, not be swallowed, and the stages
    # already committed must stay committed.
    db, origin = built
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")

    class Exploding:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, request: CompletionRequest) -> CompletionResult:
            self.calls += 1
            if "S " in request.content and " M " in request.content:
                raise RuntimeError("the judge exploded")
            return CompletionResult("a brief body here", Usage(1, 1))

    with pytest.raises(StageFailed, match="the judge exploded") as failed:
        _run(db, tmp_path, Exploding())

    # the failure names its stage and carries the stages that finished
    assert failed.value.stage == "propagate"
    assert [s["op"] for s in failed.value.outcome["stages"]] == ["update"]

    # update and condense ran before propagate and their work survives
    assert _uncondensed(db) == 0


def test_propagate_runs_before_the_leaf_is_re_briefed(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # the order is the whole reason this is one op. `propagate` judges a leaf's
    # NEW content against its STORED brief; re-briefing first rewrites that
    # brief with the current signature, so nothing is ever judged and no
    # ancestor is ever marked stale — the upper levels keep describing content
    # that changed underneath them, silently.
    db, origin = built
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    judge = Judge()

    outcome = _run(db, tmp_path, judge)

    assert outcome["judged"] > 0  # something was actually judged


def test_repair_is_reached(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # repair is the stage that acts on what monitor measured; deleting it from
    # the chain changed nothing any test could see.
    db, origin = built
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    reached: list[int] = []

    def labeler(vectors: object) -> list[int]:
        reached.append(len(vectors))  # type: ignore[arg-type]
        return [0] * len(vectors)  # type: ignore[arg-type]

    sync(
        _job("sync-tree"),
        job_context(db, tmp_path),
        encoder_for=fake_encoder,
        client=Judge(),
        core_labeler=labeler,
    )

    with db.connect() as conn:
        rate_rows = conn.execute(
            "SELECT COUNT(*) FROM misfit WHERE tree = ?", (TREE,)
        ).fetchone()[0]
    assert rate_rows > 0  # monitor fed repair something to act on


def test_a_declining_judge_makes_the_run_incomplete(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # a whole-panel abstention is reachable and must be reported. One verb
    # over six stages must say when it did less than it was asked.
    db, origin = built
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")

    outcome = _run(db, tmp_path, Judge(verdict="I cannot determine that"))

    assert outcome["abstained"] > 0
    assert outcome["incomplete"] is True


def test_repair_acts_on_what_it_finds(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # repair is the stage that ACTS on what monitor measured. A healthy little
    # tree gives it nothing to do, so deleting it from the chain was invisible;
    # this plants a cluster it must dissolve (below two members) and asserts it
    # is gone afterwards.
    db, origin = built
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    with db.connect() as conn, conn:
        victim = conn.execute(
            "SELECT m.section_id AS s, m.node_id AS n FROM node_members m "
            "JOIN nodes o ON o.id = m.node_id WHERE o.level = 0 LIMIT 1"
        ).fetchone()
        lonely = cluster_store.add_leaf_node(
            conn, TREE, [(int(victim["s"]), False, None)]
        )
        conn.execute(
            "DELETE FROM node_members WHERE node_id = ? AND section_id = ?",
            (int(victim["n"]), int(victim["s"])),
        )
    assert lonely in _node_ids(db)

    _run(db, tmp_path, Judge())

    assert lonely not in _node_ids(db)  # dissolved, its member re-placed


def test_a_run_over_an_unchanged_corpus_says_nothing_changed(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # "succeeded" is not an answer to "did anything happen?".
    db, _origin = built

    outcome = _run(db, tmp_path, Judge())

    assert outcome["changed"] is False


def _unembedded_condensations(conn: object) -> int:
    texts = conn.execute("SELECT text FROM condensations").fetchall()  # type: ignore[attr-defined]
    return sum(
        1
        for row in texts
        if conn.execute(  # type: ignore[attr-defined]
            "SELECT 1 FROM embeddings WHERE content_hash = ?",
            (content_hash(row["text"].encode("utf-8")),),
        ).fetchone()
        is None
    )


def test_a_tree_built_today_synced_twice_unchanged_calls_no_model(
    built: tuple[Database, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # the first sync after a build places by condensation vectors the build
    # never embedded; if it moved anything it would rewrite briefs for a source
    # that did not change, and the second would move the next misfit
    db, _origin = built
    judge = Judge()
    with db.connect() as conn, conn:
        # a tree built before condensations were embedded
        for row in conn.execute("SELECT text FROM condensations").fetchall():
            conn.execute(
                "DELETE FROM embeddings WHERE content_hash = ?",
                (content_hash(row["text"].encode("utf-8")),),
            )

    # the toy's vectors are all alike, so nothing would move either way; what
    # is checked is that the monitor (and the baseline it captures) and repair
    # read the condensations' space, not the one the last embed replaces
    unembedded: list[int] = []

    def measured(job: Job, context: object) -> object:
        with db.connect() as conn:
            unembedded.append(_unembedded_condensations(conn))
        return monitor(job, context)

    monkeypatch.setattr(sync_chain, "monitor", measured)
    for _ in range(2):
        outcome = _run(db, tmp_path, judge)

        assert outcome["changed"] is False
        assert judge.calls == 0
    assert unembedded == [0, 0]


def test_a_forced_assignment_is_counted(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # a force-assign is the system deciding that an alien member is better than
    # an unreachable one — a real judgement call, so it must not be a silent
    # one.
    db, origin = built
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    with db.connect() as conn, conn:
        member = conn.execute(  # an UNTOUCHED file: the edit would re-place
            "SELECT m.node_id, m.section_id FROM node_members m "
            "JOIN sections s ON s.id = m.section_id "
            "WHERE s.path != 'f0.txt' LIMIT 1"
        ).fetchone()
        conn.execute(
            "UPDATE node_members SET forced = 1 WHERE node_id = ? "
            "AND section_id = ?",
            (int(member["node_id"]), int(member["section_id"])),
        )

    outcome = _run(db, tmp_path, Judge())

    assert outcome["forced"] >= 1


def _top(db: Database) -> tuple[int, int]:
    """(level, node id) of the tree's current single top."""
    with db.connect() as conn:
        row = conn.execute(
            "SELECT id, level FROM nodes WHERE tree = ? ORDER BY level DESC, "
            "id LIMIT 1",
            (TREE,),
        ).fetchone()
    return int(row["level"]), int(row["id"])


def test_sync_briefs_stale_uppers_above_level_one(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    """Sync rewrites a stale brief two floors up, not only at level 1.

    The op's scope defaults to level 1, so a chain calling ``brief_upper``
    bare would leave a stale or missing brief at level 2 or above (the
    root's included) marked by propagate and never rewritten by any sync.
    """
    db, _origin = built
    top_level, old_top = _top(db)
    with db.connect() as conn, conn:
        grafted = int(
            conn.execute(
                "INSERT INTO nodes(tree, level, label, created_at) "
                "VALUES (?, ?, 0, 't')",
                (TREE, top_level + 1),
            ).lastrowid
        )
        cluster_store.add_child(
            conn, grafted, old_top, attached=False, similarity=None
        )
    assert top_level + 1 >= 2  # the case under test: above the op's default

    _run(db, tmp_path, Judge())

    with db.connect() as conn:
        row = conn.execute(
            "SELECT text FROM briefs WHERE node_id = ?", (grafted,)
        ).fetchone()
    assert row is not None  # the level-2 top was briefed by the sync
    assert "revision" in str(row["text"])  # ... by a real completion call


def test_sync_adopts_a_leaf_even_when_repair_did_nothing(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    """A drain-emitted leaf must not wait for a settle to become reachable.

    The closing stages must run whether or not repair changed anything:
    gated on ``repaired["pinned"]``, a pin-free steady tree would leave a
    leaf the drain emitted under no parent, written to the export but
    unreachable from root.md, until the next settle or maintain.
    """
    from hrono.ingest.identity import Address, content_hash
    from hrono.ingest.store import insert_section, upsert_content
    from hrono.summarize import store as condensations

    db, _origin = built
    with db.connect() as conn, conn:
        leaf = int(
            conn.execute(
                "INSERT INTO nodes(tree, level, label, created_at) "
                "VALUES (?, 0, 0, 't')",
                (TREE,),
            ).lastrowid
        )
        for n in range(2):
            body = f"a freshly drained chunk number {n}".encode()
            digest = content_hash(body)
            upsert_content(conn, digest, body)
            condensations.upsert(conn, digest, "sonnet", "its essence", 1, 1)
            section = insert_section(
                conn,
                source="drained",  # not the git source: the diff must not
                # classify these fixture rows as deletions of real files
                address=Address("git", "x", f"drained/{n}.txt", "v"),
                start=0,
                end=len(body),
                content_hash=digest,
                ordinal=0,
            )
            cluster_store.add_member(
                conn, leaf, section, forced=False, similarity=None
            )

    _run(db, tmp_path, Judge())

    with db.connect() as conn:
        parent = conn.execute(
            "SELECT parent_id FROM node_children WHERE child_id = ?", (leaf,)
        ).fetchone()
        briefed = conn.execute(
            "SELECT 1 FROM briefs WHERE node_id = ?", (leaf,)
        ).fetchone()
    assert briefed is not None  # the sync briefed the new topic itself
    assert parent is not None  # ... and hung it under a parent, reachably


# --- insights: a sync keeps the passes (E059) ------------------------------

FINDING = {"findings": [{"statement": "Module 0 is read first"}]}
EXTENDED = "Extended with a finding: module 0 is read first."


_EXTENDS = itertools.count(1)  # each extended brief reads differently


class Insighter(Judge):
    """Judge and briefer, plus the insights review and extend calls.

    Keeps the order of the calls: a brief call is marked ``saw`` when the
    extended text was in what it was written from.
    """

    def __init__(self) -> None:
        super().__init__()
        self.log: list[str] = []

    def complete(self, request: CompletionRequest) -> CompletionResult:
        text = request.content
        if text.startswith("REVIEW"):
            self.log.append("review")
            return CompletionResult(json.dumps(FINDING), Usage(5, 2))
        if text.startswith("EXTEND"):
            self.log.append("extend")
            return CompletionResult(
                f"{EXTENDED} ({next(_EXTENDS)})", Usage(3, 2)
            )
        result = super().complete(request)
        if not ("S " in text and " M " in text):
            self.log.append("brief-saw" if "Extended with" in text else "brief")
        return result


def _insights(db: Database, threshold: int) -> None:
    """Switch insights on for the tree, with the role's model and prompts."""
    with db.write() as conn:
        registry_store.insert(
            conn,
            "models",
            "opus",
            json.dumps(
                {
                    "name": "opus",
                    "kind": "text",
                    "connection": "c",
                    "model": "claude",
                    "role": "insights",
                    "params": {},
                }
            ),
            None,
            "t",
        )
        for role, template in (
            ("insights-review", "REVIEW {brief} {index}"),
            ("insights-extend", "EXTEND {brief} {findings}"),
        ):
            registry_store.insert(
                conn,
                "prompts",
                role,
                json.dumps({"name": role, "role": role, "template": template}),
                None,
                "t",
            )
        registry_store.insert(
            conn,
            "trees",
            TREE,
            json.dumps(
                {
                    "name": TREE,
                    "sources": ["repo"],
                    "insights": True,
                    "insights_threshold": threshold,
                }
            ),
            None,
            "t",
        )


def _passes(db: Database) -> list[int]:
    with db.connect() as conn:
        return [
            int(r["node_id"])
            for r in conn.execute("SELECT node_id FROM insights_passes")
        ]


def _graft(db: Database, tmp_path: Path) -> None:
    """Give the tree a second upper level: the top gets a parent, briefed."""
    top_level, old_top = _top(db)
    with db.write() as conn:
        grafted = int(
            conn.execute(
                "INSERT INTO nodes(tree, level, label, created_at) "
                "VALUES (?, ?, 0, 't')",
                (TREE, top_level + 1),
            ).lastrowid
        )
        cluster_store.add_child(
            conn, grafted, old_top, attached=False, similarity=None
        )
    _run(db, tmp_path, Judge())  # writes the new top's brief


def _briefed_first(db: Database, tmp_path: Path) -> list[int]:
    """Review the tree once, as a build would, and name the topics passed."""
    _graft(db, tmp_path)
    _insights(db, 1)
    review.run(
        job_context(db, tmp_path),
        TREE,
        levels=[1, 2],
        root=True,
        client=Insighter(),
    )
    return sorted(set(_passes(db)))


def test_a_sync_reviews_again_a_reviewed_topic_it_rewrote_before_its_parent(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    db, origin = built
    reviewed = _briefed_first(db, tmp_path)
    assert reviewed
    with db.write() as conn:  # only the rewrite rule, never the counter
        conn.execute(
            "UPDATE registry SET config = json_set(config, "
            "'$.insights_threshold', 1000000000) WHERE collection = 'trees'"
        )
    before = len(_passes(db))
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    client = Insighter()

    outcome = _run(db, tmp_path, client)

    assert len(_passes(db)) > before  # the rewritten topic was reviewed again
    assert outcome["insights"]["reviews"] >= 1  # type: ignore[index]
    # its rewrite, then its pass, then the parent written from the result
    log = client.log
    first = log.index("review")
    assert log[first + 1] == "extend"
    assert "brief-saw" in log[first + 2 :]
    assert "brief" in log[:first]


def test_a_sync_runs_no_pass_on_a_topic_under_the_threshold(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    db, origin = built
    _insights(db, 10**9)
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    client = Insighter()

    outcome = _run(db, tmp_path, client)

    assert "review" not in client.log and _passes(db) == []
    assert outcome["insights"]["reviews"] == 0  # type: ignore[index]


def test_a_topic_reaching_the_threshold_on_a_sync_gets_its_first_pass(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    db, _origin = built
    _graft(db, tmp_path)
    _insights(db, 1)
    assert _passes(db) == []
    # nothing changed in the source: only the counter selects a pass here
    client = Insighter()

    outcome = _run(db, tmp_path, client)

    assert _passes(db) and outcome["insights"]["reviews"] >= 1  # type: ignore[index]
    assert client.log.count("review") == client.log.count("extend")
    # the level above is written from the extended brief, not the cheaper one
    assert "brief-saw" in client.log


def test_a_sync_stores_findings_for_a_pinned_reviewed_topic_and_keeps_its_brief(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    db, origin = built
    reviewed = _briefed_first(db, tmp_path)
    with db.write() as conn:
        for node in reviewed:
            pins.pin(conn, pins.BRIEF, node, reason="by hand")
        stored = {
            r["node_id"]: r["text"]
            for r in conn.execute("SELECT node_id, text FROM briefs")
            if r["node_id"] in reviewed
        }
        conn.execute(
            "UPDATE registry SET config = json_set(config, "
            "'$.insights_threshold', 1) WHERE collection = 'trees'"
        )
        before = conn.execute(
            "SELECT COUNT(*) FROM insights_findings"
        ).fetchone()[0]
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")

    _run(db, tmp_path, Insighter())

    with db.connect() as conn:
        after = conn.execute(
            "SELECT COUNT(*) FROM insights_findings"
        ).fetchone()[0]
        kept = {
            r["node_id"]: r["text"]
            for r in conn.execute("SELECT node_id, text FROM briefs")
            if r["node_id"] in reviewed
        }
    assert kept == stored  # byte for byte
    assert after > before  # a new pass ran and stored its findings
    with db.connect() as conn:
        skipped = {
            r["skipped"]
            for r in conn.execute(
                "SELECT skipped FROM insights_passes ORDER BY id DESC LIMIT 1"
            )
        }
    assert skipped == {"pinned"}  # ... and was not applied


def test_a_sync_with_insights_off_calls_no_insights_model(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    db, origin = built
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    client = Insighter()

    outcome = _run(db, tmp_path, client)

    assert "insights" not in outcome and "review" not in client.log


class Outage(Insighter):
    """The insights provider is down: every review call fails."""

    def complete(self, request: CompletionRequest) -> CompletionResult:
        if request.content.startswith("REVIEW"):
            raise LLMError("the insights provider is down")
        return super().complete(request)


def test_a_failed_pass_stops_the_sync_and_the_next_sync_reviews_again(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    db, origin = built
    reviewed = _briefed_first(db, tmp_path)
    with db.write() as conn:  # only the rewrite rule, never the counter
        conn.execute(
            "UPDATE registry SET config = json_set(config, "
            "'$.insights_threshold', 1000000000) WHERE collection = 'trees'"
        )
    before = len(_passes(db))
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")

    # a provider error is not "nothing to review": the sync fails, named
    with pytest.raises(StageFailed, match="provider is down") as failed:
        _run(db, tmp_path, Outage())
    assert failed.value.stage == "brief-upper"
    assert len(_passes(db)) == before  # no pass stored for the failed call

    # the next sync, with nothing new in the source, reviews the rewritten
    # topic it could not review and writes its parent from the result
    client = Insighter()
    outcome = _run(db, tmp_path, client)

    assert len(_passes(db)) > before and reviewed
    assert outcome["insights"]["reviews"] >= 1  # type: ignore[index]
    assert "brief-saw" in client.log[client.log.index("extend") :]
