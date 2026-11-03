"""The insights pass: a read-only review, then the brief extended in place.

One real database, one fake model (the project's `Completion` seam). The fake
plays the reviewer by calling the lookups it is given, so what a review could
read is what the test asserts, not what a mock says.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono import pins
from hrono.db.database import Database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.jobs import store as jobs_store
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.jobs.stages import StageFailed
from hrono.jobs.worker import Worker, enqueue
from hrono.llm.client import (
    CompletionRequest,
    CompletionResult,
    LLMError,
    Unfinished,
    Usage,
)
from hrono.registry import store as registry_store
from hrono.server.ui.reviewed import reviewed as topic_view
from hrono.summarize import briefs, insights, review
from hrono.summarize import store as condensations
from hrono.summarize.brief_upper import brief_upper
from hrono.summarize.build_tree import build_tree
from hrono.summarize.resolve import (
    NO_INSIGHTS_MODEL,
    resolve_text_model,
    template_hash,
)
from hrono.tree.settle import settle

TREE = "default"
CHEAP = "A topic that gathers the signing code."
FINDINGS = {
    "findings": [
        {
            "statement": "Signing skips unsigned drafts",
            "angle": "rules",
            "why": "a copy of the newest member would sign them",
            "evidence": [{"file": "a.py", "lines": "1-3", "version": "guess"}],
            "placement": "not stated; the area",
            "confidence": "high",
        }
    ],
    "dropped": ["b.py retries: it does not, checked"],
    "looked": "a.py, b.py",
}
EXTENDED = CHEAP + " Signing skips unsigned drafts (a.py:1-3)."


class Reviewer:
    """Answers the review with findings, the extend call with a brief."""

    def __init__(
        self,
        findings: object = FINDINGS,
        fail: Exception | None = None,
        probe: str = "c.py",
    ) -> None:
        self.findings = findings
        self.fail = fail
        self.probe = probe
        self.reviews = 0
        self.extends = 0
        self.upper: list[str] = []
        self.saw: dict[str, str] = {}
        self.models: list[str] = []

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.models.append(str(request.model["name"]))
        content = request.content
        if content.startswith("REVIEW"):
            self.reviews += 1
            if request.tools is not None:
                for path in ("source/repo/a.py", f"source/repo/{self.probe}"):
                    self.saw[path] = request.tools.call("Read", {"path": path})
                self.saw["grep"] = request.tools.call("Grep", {"pattern": "."})
                self.saw["most"] = str(request.tools.most)
            if self.fail is not None:
                raise self.fail
            return CompletionResult(
                "```json\n" + json.dumps(self.findings) + "\n```", Usage(9, 3)
            )
        if content.startswith("EXTEND"):
            self.extends += 1
            return CompletionResult(EXTENDED, Usage(4, 2))
        self.upper.append(content)
        return CompletionResult(
            "An area made of the parts below it, summarised.", Usage(1, 1)
        )


def _row(conn: object, table: str, name: str, **config: object) -> None:
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        table,
        name,
        json.dumps({"name": name, **config}),
        None,
        "t",
    )


def _section(
    conn: object,
    path: str,
    body: bytes,
    i: int,
    source: str = "repo",
    version: str = "v1",
) -> int:
    istore.upsert_content(conn, content_hash(body), body)  # type: ignore[arg-type]
    found = istore.insert_section(
        conn,  # type: ignore[arg-type]
        source=source,
        address=Address("git", f"example.com/{source}", path, version),
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=i,
    )
    condensations.upsert(
        conn,  # type: ignore[arg-type]
        content_hash(body),
        "cond",
        f"RULE condensation of {path}",
        10,
        3,
    )
    return found


def _node(conn: object, level: int, text: str) -> int:
    node = int(
        conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, ?, -1, 't')",
            (TREE, level),
        ).lastrowid
    )
    briefs.upsert(
        conn,  # type: ignore[arg-type]
        node,
        text,
        model_name="cheap",
        prompt_name="brief-upper",
        prompt_hash="h",
        member_signature=f"s{node}",
        input_tokens=1,
        output_tokens=1,
    )
    return node


@pytest.fixture
def world(tmp_path: Path) -> Iterator[tuple[Database, dict[str, int]]]:
    """root <- (mid <- (a, b), c): a.py and b.py under mid, c.py outside."""
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        _row(conn, "models", "cond", kind="text", role="condense", model="m")
        _row(
            conn, "models", "cheap", kind="text", role="brief-upper", model="m"
        )
        _row(conn, "models", "opus", kind="text", role="insights", model="m")
        _row(conn, "prompts", "up", role="brief-upper", template="UP {content}")
        _row(
            conn,
            "prompts",
            "review",
            role="insights-review",
            template="REVIEW {brief} {index}",
        )
        _row(
            conn,
            "prompts",
            "extend",
            role="insights-extend",
            template="EXTEND {brief} {findings}",
        )
        _row(
            conn,
            "trees",
            TREE,
            sources=["repo"],
            insights=True,
            insights_threshold=10,
        )
        ids = {}
        for number, name in enumerate(("a.py", "b.py", "c.py")):
            ids[name] = _section(conn, name, f"{name} body\n".encode(), number)
        a = _node(conn, 0, "Topic a handles signing of drafts.")
        b = _node(conn, 0, "Topic b handles retries.")
        c = _node(conn, 0, "Topic c handles the outside world.")
        mid = _node(conn, 1, CHEAP)
        root = _node(conn, 2, "The whole area, in one place.")
        for node, name in ((a, "a.py"), (b, "b.py"), (c, "c.py")):
            conn.execute(
                "INSERT INTO node_members(node_id, section_id, forced, "
                "attached, created_at) VALUES (?, ?, 0, 0, 't')",
                (node, ids[name]),
            )
        for parent, kids in ((mid, (a, b)), (root, (mid, c))):
            for kid in kids:
                conn.execute(
                    "INSERT INTO node_children(parent_id, child_id, attached, "
                    "created_at) VALUES (?, ?, 0, 't')",
                    (parent, kid),
                )
    yield database, {"a": a, "b": b, "c": c, "mid": mid, "root": root}
    database.close()


def _run(
    database: Database,
    reviewer: Reviewer,
    levels: list[int],
    root: bool = False,
    rebrief: object = None,
) -> dict[str, object]:
    return review.run(
        JobContext(database),
        TREE,
        levels=levels,
        root=root,
        client=reviewer,
        rebrief=rebrief,  # type: ignore[arg-type]
    )


def _text(database: Database, node: int) -> str:
    with database.connect() as conn:
        return str(briefs.get(conn, node)["text"])  # type: ignore[index]


def _count(database: Database, sql: str) -> int:
    with database.connect() as conn:
        return int(conn.execute(sql).fetchone()[0])


def test_a_review_stores_its_findings_and_reads_only_its_subtree(world) -> None:  # type: ignore[no-untyped-def]
    database, ids = world
    reviewer = Reviewer()

    done = _run(database, reviewer, [1])

    assert done["reviews"] == 1 and done["findings"] == 1
    with database.connect() as conn:
        found = conn.execute(
            "SELECT f.*, p.dropped, p.looked, p.node_id, p.skipped "
            "FROM insights_findings f JOIN insights_passes p "
            "ON p.id = f.pass_id"
        ).fetchall()
    assert len(found) == 1
    row = found[0]
    assert row["node_id"] == ids["mid"] and row["skipped"] == ""
    assert row["statement"] == "Signing skips unsigned drafts"
    # the version is the file's synced one, not what the reviewer wrote
    assert json.loads(row["evidence"]) == [
        {"file": "a.py", "lines": "1-3", "version": "v1"}
    ]
    assert row["confidence"] == "high" and "area" in row["placement"]
    assert json.loads(row["dropped"]) == FINDINGS["dropped"]
    # the lookups: its own file is readable, a file under another topic is not
    assert "a.py body" in reviewer.saw["source/repo/a.py"]
    assert reviewer.saw["source/repo/c.py"].startswith("No such file")
    assert "c.py" not in reviewer.saw["grep"]
    assert reviewer.saw["most"] == str(review.MOST_LOOKUPS)


def test_evidence_outside_the_area_gets_no_version(world) -> None:  # type: ignore[no-untyped-def]
    database, _ = world
    found = {
        "findings": [
            {
                "statement": "s",
                "evidence": [
                    {"file": "c.py", "version": "guess"},
                    {"file": "a.py"},
                    {"file": "source/repo/b.py", "lines": "1"},
                    {"file": "condensed/repo/b.py.md"},
                ],
            }
        ]
    }

    _run(database, Reviewer(findings=found), [1])

    with database.connect() as conn:
        stored = json.loads(
            conn.execute("SELECT evidence FROM insights_findings").fetchone()[0]
        )
    # a file named as the lookups print it (`source/<source>/<path>`) too
    assert stored == [
        {"file": "c.py"},
        {"file": "a.py", "version": "v1"},
        {"file": "source/repo/b.py", "lines": "1", "version": "v1"},
        {"file": "condensed/repo/b.py.md", "version": "v1"},
    ]


def test_a_path_two_sources_hold_gets_the_version_of_the_source_it_names(
    world,  # type: ignore[no-untyped-def]
) -> None:
    database, ids = world
    with database.connect() as conn, conn:
        twin = _section(conn, "a.py", b"other a body\n", 9, "other", "v2")
        conn.execute(
            "INSERT INTO node_members(node_id, section_id, forced, attached, "
            "created_at) VALUES (?, ?, 0, 0, 't')",
            (ids["b"], twin),
        )
    found = {
        "findings": [
            {
                "statement": "s",
                "evidence": [
                    {"file": "a.py"},
                    {"file": "b.py"},
                    {"file": "source/repo/a.py"},
                    {"file": "source/other/a.py"},
                ],
            }
        ]
    }

    _run(database, Reviewer(findings=found), [1])

    with database.connect() as conn:
        stored = json.loads(
            conn.execute("SELECT evidence FROM insights_findings").fetchone()[0]
        )
    assert stored == [
        {"file": "a.py"},  # two sources hold it: which one is not said
        {"file": "b.py", "version": "v1"},
        {"file": "source/repo/a.py", "version": "v1"},
        {"file": "source/other/a.py", "version": "v2"},
    ]


def _settle(database: Database, reviewer: Reviewer) -> dict[str, object]:
    job = Job("s", None, TREE, "settle", {}, "running", None, "t", "t")
    return dict(settle(job, JobContext(database), client=reviewer))


def test_an_untripped_settle_reviews_what_is_due_root_last_and_only_that(
    world,
) -> None:  # type: ignore[no-untyped-def]
    database, ids = world
    reviewer = Reviewer()

    done = _settle(database, reviewer)

    assert done["settled"] is False and done["insights"]["reviews"] == 2  # type: ignore[index]
    with database.connect() as conn:
        reviewed = [
            int(r[0])
            for r in conn.execute(
                "SELECT node_id FROM insights_passes ORDER BY passed_at, id"
            )
        ]
    assert reviewed == [ids["mid"], ids["root"]]
    # only the reviewed topic's parent (the root) was briefed again
    assert len(reviewer.upper) == 1

    again = Reviewer()
    quiet = _settle(database, again)
    assert quiet == {
        "settled": False,
        "held": 0,
        "released": 0,
        "stages": [],
    }
    assert again.models == []


def test_an_untripped_settle_with_nothing_to_review_calls_no_model(
    world,
) -> None:  # type: ignore[no-untyped-def]
    database, _ = world
    nothing = {"settled": False, "held": 0, "released": 0, "stages": []}
    with database.write() as conn:
        conn.execute(
            "UPDATE registry SET config = json_set(config, '$.insights', 0) "
            "WHERE collection = 'trees'"
        )
    off = Reviewer()
    assert _settle(database, off) == nothing and off.models == []

    with database.write() as conn:
        conn.execute(
            "UPDATE registry SET config = json_set(config, '$.insights', 1) "
            "WHERE collection = 'trees'"
        )
        conn.execute("DELETE FROM registry WHERE name = 'opus'")
    nomodel = Reviewer()
    assert _settle(database, nomodel) == nothing and nomodel.models == []


def test_the_extend_call_rewrites_the_brief_and_keeps_the_cheaper_one(
    world,
) -> None:  # type: ignore[no-untyped-def]
    database, ids = world

    _run(database, Reviewer(), [1])

    assert _text(database, ids["mid"]) == EXTENDED
    with database.connect() as conn:
        kept = briefs.versions(conn, ids["mid"])
        covered = insights.unreviewed(conn, TREE)
    assert [(v["text"], v["reason"], v["reviewer"]) for v in kept] == [
        (CHEAP, "insights", "opus")
    ]
    # the brief the pass left is covered by it, not counted as new
    assert covered[ids["root"]] == len("Topic c handles the outside world.")


def test_a_later_brief_upper_leaves_the_extended_brief_alone(world) -> None:  # type: ignore[no-untyped-def]
    database, ids = world
    _run(database, Reviewer(), [1])
    with database.write() as conn:  # as the cheap role stored it
        conn.execute(
            "UPDATE briefs SET prompt_hash = ?, member_signature = ? "
            "WHERE node_id = ?",
            (
                template_hash("UP {content}"),
                briefs.member_signature(conn, ids["mid"]),
                ids["mid"],
            ),
        )
    cheap = Reviewer()
    brief_upper(
        Job(
            "u",
            None,
            TREE,
            "brief-upper",
            {"level": 1},
            "running",
            None,
            "t",
            "t",
        ),
        JobContext(database),
        client=cheap,
    )

    assert _text(database, ids["mid"]) == EXTENDED
    assert cheap.upper == []


def test_a_pinned_brief_is_kept_byte_for_byte_and_the_findings_are_marked(
    world,
) -> None:  # type: ignore[no-untyped-def]
    database, ids = world
    with database.write() as conn:
        pins.pin(conn, pins.BRIEF, ids["mid"], reason="by hand")
    reviewer = Reviewer()

    done = _run(database, reviewer, [1])

    assert _text(database, ids["mid"]) == CHEAP
    assert reviewer.reviews == 1 and reviewer.extends == 0
    assert done["findings"] == 1 and done["extends"] == 0
    with database.connect() as conn:
        row = conn.execute("SELECT skipped FROM insights_passes").fetchone()
        assert row["skipped"] == "pinned"
        assert briefs.versions(conn, ids["mid"]) == []
    assert _count(database, "SELECT COUNT(*) FROM insights_findings") == 1


@pytest.mark.parametrize(
    "failure",
    [Unfinished("the model kept calling tools past its budget"), None],
    ids=["turn cap", "not findings"],
)
def test_a_review_that_does_not_finish_stores_nothing_and_says_why(  # type: ignore[no-untyped-def]
    world, failure, caplog
) -> None:
    database, ids = world
    reviewer = Reviewer(findings="no json here", fail=failure)
    if failure is None:
        reviewer.findings = None

    with caplog.at_level("WARNING", logger="hrono.insights"):
        done = _run(database, reviewer, [1])

    assert done["reviews"] == 0 and len(done["failed"]) == 1  # type: ignore[arg-type]
    assert _text(database, ids["mid"]) == CHEAP
    assert _count(database, "SELECT COUNT(*) FROM insights_passes") == 0
    assert _count(database, "SELECT COUNT(*) FROM insights_findings") == 0
    assert "no review stored" in caplog.text
    # not covered: the topic is due again
    with database.connect() as conn:
        assert [p.node for p in insights.due(conn, TREE, 1, 10, False)] == [
            ids["mid"]
        ]


def test_a_provider_error_stops_the_run_naming_the_topic(world) -> None:  # type: ignore[no-untyped-def]
    database, ids = world
    with pytest.raises(LLMError) as raised:
        _run(database, Reviewer(fail=LLMError("rate limited")), [1])
    assert review.review_item(ids["mid"]) in "".join(raised.value.__notes__)
    assert _count(database, "SELECT COUNT(*) FROM insights_passes") == 0


def test_a_failed_review_in_a_settle_names_the_topic_on_the_failed_run(
    world,  # type: ignore[no-untyped-def]
) -> None:
    database, ids = world
    with pytest.raises(StageFailed) as raised:
        _settle(database, Reviewer(fail=LLMError("rate limited")))
    assert raised.value.stage == "review"
    assert raised.value.item == review.review_item(ids["mid"])


def test_a_settle_the_provider_failed_shows_on_the_reviewed_topic(
    world,  # type: ignore[no-untyped-def]
) -> None:
    """Review now end to end: the worker records the failed settle, and the
    topic's view finds that run (what its page links as "See the run")."""
    database, ids = world
    failing = Reviewer(fail=LLMError("the model server returned 500"))
    worker = Worker(
        database, {"settle": lambda job, ctx: settle(job, ctx, client=failing)}
    )
    worker.start()
    try:
        job_id = enqueue(database, "settle", {}, tree=TREE)
        deadline = time.monotonic() + 10
        status = None
        while status not in ("failed", "succeeded"):
            assert time.monotonic() < deadline, f"settle still {status}"
            with database.connect() as conn:
                status = jobs_store.get(conn, job_id)["status"]
            time.sleep(0.01)
    finally:
        worker.stop()
        worker.join(timeout=5)

    assert status == "failed"
    with database.connect() as conn:
        seen = topic_view(conn, TREE, ids["mid"], "mid", "", str)
    assert seen is not None and seen["failed"] == job_id
    assert (
        seen["reviewed"] is False
    )  # no pass stored: "found nothing" stays off


def test_without_an_insights_model_nothing_runs_and_it_says_why(world) -> None:  # type: ignore[no-untyped-def]
    database, _ = world
    with database.write() as conn:
        conn.execute("DELETE FROM registry WHERE name = 'opus'")
    reviewer = Reviewer()

    done = _run(database, reviewer, [1, 2], root=True)

    assert done["note"] == NO_INSIGHTS_MODEL and done["reviews"] == 0
    assert reviewer.models == []
    # and the sole text model is not a stand-in for it
    with (
        database.connect() as conn,
        pytest.raises(LLMError, match="role insights"),
    ):
        resolve_text_model(conn, {}, "insights")


def _write(conn: object, node: int, text: str, reason: str) -> None:
    briefs.upsert(
        conn,  # type: ignore[arg-type]
        node,
        text,
        model_name="cheap",
        prompt_name="p",
        prompt_hash="h",
        member_signature="s",
        input_tokens=0,
        output_tokens=0,
        reason=reason,
    )


def _kept(database: Database, node: int) -> list[tuple[str, str]]:
    with database.connect() as conn:
        return [(v["text"], v["reason"]) for v in briefs.versions(conn, node)]


def test_many_passes_never_push_the_cheaper_brief_out_of_history(
    world,
) -> None:  # type: ignore[no-untyped-def]
    database, ids = world
    mid = ids["mid"]
    with database.write() as conn:
        # an earlier cycle: a rewrite, then a pass, then the brief written again
        _write(conn, mid, "rewritten by hand", "rewrite")
        _write(conn, mid, "extended once", "insights")
        _write(conn, mid, "written again", "regen")
        # this cycle: the cheaper brief, then six passes with nothing between
        for i in range(briefs.KEEP_VERSIONS + 1):
            _write(conn, mid, f"extended {i}", "insights")
    kept = _kept(database, mid)
    assert ("written again", "insights") in kept
    assert len(kept) == briefs.KEEP_VERSIONS + 1
    # the cheaper brief of an earlier cycle is not kept for ever
    assert "extended once" not in [text for text, _ in kept]


def test_a_brief_written_again_after_the_passes_is_kept_like_any_other(
    world,
) -> None:  # type: ignore[no-untyped-def]
    database, ids = world
    mid = ids["mid"]
    with database.write() as conn:
        _write(conn, mid, "extended", "insights")
        for i in range(briefs.KEEP_VERSIONS + 3):
            _write(conn, mid, f"regenerated {i}", "regen")
    kept = _kept(database, mid)
    assert len(kept) == briefs.KEEP_VERSIONS
    assert CHEAP not in [text for text, _ in kept]


def test_six_passes_in_a_row_keep_the_cheaper_brief_a_reader_compares(
    world,
) -> None:  # type: ignore[no-untyped-def]
    """Each sync rewrites the brief cheaply, then a pass extends it."""
    database, ids = world
    _run(database, Reviewer(), [1])
    for i in range(5):
        with database.write() as conn:
            briefs.upsert(
                conn,
                ids["mid"],
                f"{CHEAP} Regenerated {i}.",
                model_name="cheap",
                prompt_name="p",
                prompt_hash="h",
                member_signature="s",
                input_tokens=0,
                output_tokens=0,
            )
        done = _run(database, Reviewer(), [1])
        assert done["reviews"] == 1  # the rewritten brief is reviewed again

    assert _count(database, "SELECT COUNT(*) FROM insights_passes") == 6
    with database.connect() as conn:
        kept = briefs.versions(conn, ids["mid"])
    cheaper = [v["text"] for v in kept if v["reason"] == "insights"]
    # a brief written again between passes starts a new run: only the
    # newest cheaper briefs are kept, the oldest cycle's is not kept for ever
    assert f"{CHEAP} Regenerated 4." in cheaper
    assert CHEAP not in cheaper
    assert len(kept) <= briefs.KEEP_VERSIONS + 1
    assert _text(database, ids["mid"]) == EXTENDED


def test_the_root_is_reviewed_once_and_again_only_when_something_changed(
    world,
) -> None:  # type: ignore[no-untyped-def]
    database, ids = world
    first = Reviewer()
    _run(database, first, [1, 2], root=True)
    assert first.reviews == 2  # mid by the threshold, then the root

    again = Reviewer()
    assert _run(database, again, [1, 2], root=True)["reviews"] == 0
    with database.connect() as conn:
        assert insights.passes_for(conn, TREE, 10) == ()

    with database.write() as conn:  # a brief under the root is rewritten
        briefs.upsert(
            conn,
            ids["c"],
            "Topic c now handles something else entirely.",
            model_name="cheap",
            prompt_name="p",
            prompt_hash="h",
            member_signature="new",
            input_tokens=0,
            output_tokens=0,
        )
    with database.connect() as conn:
        assert [p.node for p in insights.passes_for(conn, TREE, 10**6)] == [
            ids["root"]
        ]


def test_the_parent_is_briefed_from_the_extended_brief(world) -> None:  # type: ignore[no-untyped-def]
    database, ids = world
    cheap = Reviewer()
    context = JobContext(database)

    _run(
        database,
        Reviewer(),
        [1],
        rebrief=lambda level: brief_upper(
            Job(
                "u",
                None,
                TREE,
                "brief-upper",
                {"level": level},
                "running",
                None,
                "t",
                "t",
            ),
            context,
            client=cheap,
        ),
    )

    assert len(cheap.upper) == 1
    assert f"=== {EXTENDED} ===" in cheap.upper[0]
    assert f"=== {CHEAP} ===" not in cheap.upper[0]


def test_a_pass_below_a_reviewed_parent_gives_the_parent_a_new_pass(
    world,
) -> None:  # type: ignore[no-untyped-def]
    """Briefing the parent again drops its own pass's extension: review it."""
    database, ids = world
    cheap = Reviewer()
    context = JobContext(database)

    def rebrief(level: int) -> None:
        brief_upper(
            Job(
                "u",
                None,
                TREE,
                "brief-upper",
                {"level": level},
                "running",
                None,
                "t",
                "t",
            ),
            context,
            client=cheap,
        )

    with database.write() as conn:  # only the root reaches it at first
        conn.execute(
            "UPDATE registry SET config = json_set(config, "
            "'$.insights_threshold', 1000) WHERE collection = 'trees'"
        )
    _run(database, Reviewer(), [1, 2], root=True, rebrief=rebrief)
    assert _text(database, ids["root"]) == EXTENDED
    with database.write() as conn:  # the admin lowers the threshold
        conn.execute(
            "UPDATE registry SET config = json_set(config, "
            "'$.insights_threshold', 10) WHERE collection = 'trees'"
        )
        planned = [p.node for p in insights.passes_for(conn, TREE, 10)]

    again = Reviewer()
    done = _run(database, again, [1, 2], root=True, rebrief=rebrief)

    assert planned == [ids["mid"], ids["root"]]
    assert done["reviews"] == 2 and again.reviews == 2
    assert _text(database, ids["root"]) == EXTENDED


def test_a_tree_stored_without_a_threshold_does_not_pass_every_topic(
    world,
) -> None:  # type: ignore[no-untyped-def]
    database, _ = world
    with database.write() as conn:
        conn.execute(
            "UPDATE registry SET config = json_remove(config, "
            "'$.insights_threshold') WHERE collection = 'trees'"
        )
    reviewer = Reviewer()
    done = _run(database, reviewer, [1, 2], root=True)
    assert done["reviews"] == 1  # the root's own pass, no topic under it


def test_with_the_step_off_a_build_makes_no_insights_call(world) -> None:  # type: ignore[no-untyped-def]
    database, ids = world
    with database.write() as conn:
        conn.execute(
            "UPDATE registry SET config = json_set(config, '$.insights', 0) "
            "WHERE collection = 'trees'"
        )
    context = JobContext(database)
    reviewer = Reviewer()
    job = Job("bt", None, TREE, "build-tree", {}, "running", None, "t", "t")

    result = build_tree(job, context, client=reviewer)

    assert result == {} and reviewer.models == []
    assert (
        _count(
            database, "SELECT COUNT(*) FROM llm_calls WHERE role = 'insights'"
        )
        == 0
    )
    assert _text(database, ids["mid"]) == CHEAP


def test_a_build_with_the_step_on_runs_the_passes_the_counter_selects(
    world,
) -> None:  # type: ignore[no-untyped-def]
    database, ids = world
    context = JobContext(database)
    reviewer = Reviewer()
    job = Job("bt", None, TREE, "build-tree", {}, "running", None, "t", "t")

    result = build_tree(job, context, client=reviewer)

    assert result["insights"]["reviews"] == 2  # type: ignore[index]
    assert result["insights"]["extends"] == 2  # type: ignore[index]
    assert result["insights"]["findings"] == 2  # type: ignore[index]
    # each pass: a review (9 in, 3 out) and an extend (4 in, 2 out)
    assert result["insights"]["tokens"] == {"input": 26, "output": 10}  # type: ignore[index]
    with database.connect() as conn:
        passed = sorted(
            r["node_id"]
            for r in conn.execute("SELECT node_id FROM insights_passes")
        )
    assert passed == sorted([ids["mid"], ids["root"]])
    assert (
        _count(
            database, "SELECT COUNT(*) FROM llm_calls WHERE role = 'insights'"
        )
        == 4
    )  # a review and an extend for each

    again = Reviewer()
    quiet = build_tree(job, context, client=again)
    assert quiet["insights"]["reviews"] == 0 and again.models == []  # type: ignore[index]


def test_a_sync_does_not_spend_on_passes_unasked(world) -> None:  # type: ignore[no-untyped-def]
    database, _ = world
    reviewer = Reviewer()
    job = Job("bt", None, TREE, "build-tree", {}, "running", None, "t", "t")

    build_tree(job, JobContext(database), client=reviewer, reviewing=False)

    assert reviewer.models == []


@pytest.mark.parametrize(
    "text, count",
    [
        ('{"findings": []}', 0),
        ('Here: {"findings": [{"statement": "x"}, {"nope": 1}]} done', 1),
        ('{"findings": [{"statement": "s", "evidence": ["a.py"]}]}', 1),
        # a brace in the prose around the answer does not lose the review
        ('I read {app.config}: {"findings": [{"statement": "x"}]}', 1),
        ('{"findings": [{"statement": "x"}]} (unchecked: {g})', 1),
    ],
)
def test_the_answer_is_read_where_the_model_put_it(
    text: str, count: int
) -> None:
    assert len(review.parse(text).findings) == count


def test_an_answer_with_no_findings_list_is_not_an_answer() -> None:
    with pytest.raises(Unfinished):
        review.parse("I found several things, listed below.")


def test_a_brief_that_contains_a_placeholder_is_not_filled_twice() -> None:
    out = review.fill("A {brief} B {index}", brief="{index}", index="I")
    assert out == "A {index} B I"
