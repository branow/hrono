"""#137: one op brings a tree up to date, in the order the stages require."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster import store as cluster_store
from hrono.db.database import Database
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS
from hrono.jobs.stages import StageFailed
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.registry import store as registry_store
from hrono.tree.maintain import maintain
from hrono.tree.sync_chain import sync
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


@pytest.fixture
def built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Database, Path]]:
    monkeypatch.chdir(tmp_path)
    origin = tmp_path / "src-repo"
    url = make_repo(origin)
    database = Database.at(tmp_path / "hrono.db")
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
        job_context(database, tmp_path),
        encoder_for=fake_encoder,
        client=Judge(),
        build=fake_build,
    )
    yield database, origin
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


def test_registered_under_its_own_name() -> None:
    # `sync` is already the per-source ingest op, so the chain is `sync-tree`,
    # matching `build-tree`'s shape.
    assert "sync-tree" in OPS
    assert OPS["sync"] is not OPS["sync-tree"]


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
    assert _uncondensed(db) == 0  # #122's invariant: nothing unsummarised
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
    # one verb over six stages is a black box unless it reports (#132).
    db, origin = built
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")

    outcome = _run(db, tmp_path, Judge())

    # every stage that makes a judgement contributes its counts (#133)
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
        # makes two in its place, and until #200 nothing briefed or re-parented
        # them — the run ended leaving them beside the tree, under no root
        "adopted",
        "settle_due",
        "incomplete",
        # what the run did to the map, and each stage with its time (#213)
        "tree",
        "stages",
    }
    assert [stage["op"] for stage in outcome["stages"]] == [
        "update",
        "propagate",
        "brief",
        "brief-upper",
        "monitor",
        "repair",
        "after-repair",
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


def test_maintain_is_untouched(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # a cold build and an update are different operations with different costs;
    # conflating them is how a user accidentally pays for a rebuild.
    db, _origin = built
    before = _node_ids(db)

    maintain(
        _job("maintain"),
        job_context(db, tmp_path),
        encoder_for=fake_encoder,
        client=Judge(),
        build=fake_build,
    )

    assert _node_ids(db)  # still builds
    assert before  # and the fixture's build was real


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
    # #105 made a whole-panel abstention reachable, and #132 made it reportable.
    # One verb over six stages must say when it did less than it was asked.
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
    # #133: "succeeded" is not an answer to "did anything happen?".
    db, _origin = built

    outcome = _run(db, tmp_path, Judge())

    assert outcome["changed"] is False


def test_a_forced_assignment_is_counted(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # a force-assign is the system deciding that an alien member is better than
    # an unreachable one (#086 T35.3) — a real judgement call, and until #133 a
    # silent one.
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
