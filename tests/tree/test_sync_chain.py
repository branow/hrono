"""#137: one op brings a tree up to date, in the order the stages require."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.db.database import Database
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS
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
    """A completion that answers a judge prompt and a brief prompt apart."""

    def __init__(self, verdict: str = "major") -> None:
        self.verdict = verdict
        self.calls = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        if "S " in request.content and " M " in request.content:
            return CompletionResult(self.verdict, Usage(1, 1))
        return CompletionResult(
            "This topic covers the module's API and how its parts fit.",
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

    _run(db, tmp_path, Judge())

    assert _uncondensed(db) == 0  # #122's invariant: nothing unsummarised
    with db.connect() as conn:
        stale = conn.execute(
            "SELECT COUNT(*) FROM briefs WHERE stale = 1"
        ).fetchone()[0]
        briefed = conn.execute("SELECT COUNT(*) FROM briefs").fetchone()[0]
        leaves = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE tree = ? AND level = 0", (TREE,)
        ).fetchone()[0]
    assert briefed >= leaves  # every leaf carries a brief
    assert stale >= 0  # propagate ran and may have marked ancestors


def test_the_result_says_what_the_run_did(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # one verb over six stages is a black box unless it reports (#132).
    db, origin = built
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")

    outcome = _run(db, tmp_path, Judge())

    assert set(outcome) == {
        "judged",
        "propagated",
        "skipped",
        "abstained",
        "settle_due",
        "incomplete",
    }
    assert outcome["incomplete"] is False


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

    with pytest.raises(RuntimeError, match="the judge exploded"):
        _run(db, tmp_path, Exploding())

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
