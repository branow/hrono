import hashlib
import json
import time
from collections.abc import Iterator

import pytest

from hrono.cluster import store as cluster_store
from hrono.db.database import Database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.jobs import store as jobs_store
from hrono.jobs.model import Job, serialize_scope
from hrono.jobs.ops import JobContext
from hrono.jobs.worker import Worker
from hrono.llm import providers
from hrono.llm.client import (
    CompletionRequest,
    CompletionResult,
    LLMError,
    Usage,
)
from hrono.registry import store as registry_store
from hrono.summarize import briefs
from hrono.summarize import store as condensations
from hrono.summarize.brief import brief
from hrono.summarize.resolve import resolve_prompt, template_hash
from tests.summarize.concurrent_client import Paired

MODEL = "sonnet"
TEMPLATE = "Brief this group: {content}"
TREE = "default"


class FakeCompletion:
    def __init__(
        self,
        text: str = "The brief body describes what this topic contains.",
        fail_on: int | None = None,
    ) -> None:
        self.calls = 0
        self.contents: list[str] = []
        self._text = text
        self._fail_on = fail_on

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        self.contents.append(request.content)
        if self._fail_on == self.calls:
            raise LLMError("call failed")
        return CompletionResult(self._text, Usage(40, 12))


def register_text_model(conn: object) -> None:
    body = {
        "name": MODEL,
        "kind": "text",
        "connection": "anthropic",
        "model": "claude-sonnet-5",
        "params": {},
    }
    registry_store.insert(conn, "models", MODEL, json.dumps(body), None, "t")  # type: ignore[arg-type]


def register_brief_prompt(conn: object) -> None:
    body = {"name": "brief", "role": "brief", "template": TEMPLATE}
    registry_store.insert(conn, "prompts", "brief", json.dumps(body), None, "t")  # type: ignore[arg-type]


def add_condensed_section(conn: object, path: str, body: bytes, i: int) -> int:
    istore.upsert_content(conn, content_hash(body), body)  # type: ignore[arg-type]
    section_id = istore.insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "example.com/repo", path, "v1"),
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=i,
    )
    condensations.upsert(
        conn,  # type: ignore[arg-type]
        content_hash(body),
        MODEL,
        f"condensation of {path}",
        10,
        3,
    )
    return section_id


def job(scope: dict[str, object] | None = None) -> Job:
    return Job(
        id="b1",
        parent_id=None,
        tree=TREE,
        op="brief",
        scope=scope if scope is not None else {},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register_text_model(conn)
        register_brief_prompt(conn)
        s0 = add_condensed_section(conn, "a.py", b"aaa\n", 0)
        s1 = add_condensed_section(conn, "b.py", b"bbb\n", 1)
        s2 = add_condensed_section(conn, "c.py", b"ccc\n", 2)
        s3 = add_condensed_section(conn, "d.py", b"ddd\n", 3)
        # two bottom-level nodes: {s0,s1} and {s2,s3}
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [
                (0, s0, False, None),
                (0, s1, False, None),
                (1, s2, False, None),
                (1, s3, False, None),
            ],
            [(s0, [0.1]), (s1, [0.1]), (s2, [0.2]), (s3, [0.2])],
        )
    yield database
    database.close()


def _node_ids(db: Database) -> list[int]:
    with db.connect() as conn:
        return [
            int(r["id"])
            for r in conn.execute("SELECT id FROM nodes ORDER BY id").fetchall()
        ]


def test_writes_one_brief_per_node_with_provenance(db: Database) -> None:
    client = FakeCompletion()
    brief(job(), JobContext(db), client=client)
    assert client.calls == 2
    with db.connect() as conn:
        for node_id in _node_ids(db):
            row = briefs.get(conn, node_id)
            assert row is not None
            assert row["model_name"] == MODEL
            assert row["prompt_name"] == "brief"
            assert (
                row["prompt_hash"]
                == hashlib.sha256(TEMPLATE.encode()).hexdigest()
            )
            assert row["input_tokens"] == 40
            assert row["output_tokens"] == 12


def test_references_are_recorded_mechanically_beside_the_text(
    db: Database,
) -> None:
    # the fake LLM returns a fixed body with no URIs; every reference stored
    # therefore came from code, not the model. They stay OUT of the text:
    # recall indexes the text as passages, and a path list is dense enough to
    # outrank prose for a keyword-ish question.
    brief(job(), JobContext(db), client=FakeCompletion(text="BODY " * 12))
    nodes = _node_ids(db)
    with db.connect() as conn:
        first = briefs.get(conn, nodes[0])
        assert first is not None
        inputs = briefs.reduce_input(conn, nodes[0], MODEL)
        uris = inputs.uris
        assert uris
        assert inputs.dropped == 0  # every member reduced AND is cited
        assert json.loads(first["members"]) == list(uris)
        for uri in uris:
            assert uri not in first["text"]


def test_prompt_is_rendered_over_the_condensations(db: Database) -> None:
    client = FakeCompletion()
    brief(job(), JobContext(db), client=client)
    joined = "\n".join(client.contents)
    assert "Brief this group:" in joined
    assert "condensation of a.py" in joined
    assert "=== a.py ===" in joined  # each condensation under its file
    assert "{content}" not in joined


def test_rerun_makes_zero_llm_calls(db: Database) -> None:
    brief(job(), JobContext(db), client=FakeCompletion())
    second = FakeCompletion()
    again = brief(job(), JobContext(db), client=second)
    assert second.calls == 0
    # a run with nothing to brief reports no tokens
    assert again["briefed"] == 0
    assert "tokens" not in again


def test_a_failing_node_keeps_earlier_progress_then_rerun_fills_gap(
    db: Database,
) -> None:
    with pytest.raises(LLMError):
        brief(job(), JobContext(db), client=FakeCompletion(fail_on=2))
    with db.connect() as conn:
        stored = conn.execute("SELECT COUNT(*) FROM briefs").fetchone()[0]
    assert stored == 1
    resumed = FakeCompletion()
    brief(job(), JobContext(db), client=resumed)
    assert resumed.calls == 1
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM briefs").fetchone()[0] == 2


def test_node_without_condensations_is_skipped(db: Database) -> None:
    with db.connect() as conn, conn:
        conn.execute("DELETE FROM condensations")
    client = FakeCompletion()
    brief(job(), JobContext(db), client=client)
    assert client.calls == 0
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM briefs").fetchone()[0] == 0


def test_membership_change_marks_the_brief_stale(db: Database) -> None:
    brief(job(), JobContext(db), client=FakeCompletion())
    nodes = _node_ids(db)
    # add a new member section to the first node -> its member signature changes
    with db.connect() as conn, conn:
        new_section = add_condensed_section(conn, "e.py", b"eee\n", 9)
        conn.execute(
            "INSERT INTO node_members(node_id, section_id, attached, "
            "created_at) VALUES (?, ?, 0, 't')",
            (nodes[0], new_section),
        )
    resumed = FakeCompletion()
    brief(job(), JobContext(db), client=resumed)
    assert resumed.calls == 1  # only the node whose membership changed


def test_prompt_template_change_marks_all_briefs_stale(db: Database) -> None:
    brief(job(), JobContext(db), client=FakeCompletion())
    with db.connect() as conn, conn:
        registry_store.replace(
            conn,
            "prompts",
            "brief",
            json.dumps(
                {"name": "brief", "role": "brief", "template": "NEW {content}"}
            ),
            None,
            "t",
        )
    resumed = FakeCompletion()
    brief(job(), JobContext(db), client=resumed)
    assert resumed.calls == 2  # every brief stale under the new prompt hash


def test_counts_read_fresh_until_a_membership_changes(db: Database) -> None:
    brief(job(), JobContext(db), client=FakeCompletion())
    with db.connect() as conn:
        _, template = resolve_prompt(conn, "brief")
        fresh, stale = briefs.counts(
            conn, TREE, 0, template_hash(template), MODEL
        )
    assert (fresh, stale) == (2, 0)

    nodes = _node_ids(db)
    with db.connect() as conn, conn:
        new_section = add_condensed_section(conn, "f.py", b"fff\n", 9)
        conn.execute(
            "INSERT INTO node_members(node_id, section_id, attached, "
            "created_at) VALUES (?, ?, 0, 't')",
            (nodes[0], new_section),
        )
    with db.connect() as conn:
        fresh, stale = briefs.counts(
            conn, TREE, 0, template_hash(template), MODEL
        )
    assert (fresh, stale) == (1, 1)


class _FabricatesForA(FakeCompletion):
    """Invents an identifier for the node holding a.py, and only for it."""

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        if "a.py" in request.content:
            return CompletionResult("fabricatedToken x", Usage(40, 12))
        return CompletionResult("a plain summary", Usage(40, 12))


def test_faithfulness_gate_flags_but_does_not_block(db: Database) -> None:
    # a fabricated identifier in the LLM output is flagged, yet the brief is
    # still stored (flag policy, not hard fail); a faithful brief beside it
    # records no unfaithful tokens at all.
    brief(job(), JobContext(db), client=_FabricatesForA())
    with db.connect() as conn:
        rows = conn.execute("SELECT unfaithful FROM briefs").fetchall()
    flagged = sorted((json.loads(r["unfaithful"]) for r in rows), key=len)
    assert len(flagged) == 2  # both stored despite the fabrication
    assert flagged[0] == []
    assert "fabricatedToken" in flagged[1]


def test_runs_as_a_job_through_the_worker(
    db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hrono.summarize.brief as brief_mod

    monkeypatch.setattr(
        brief_mod,
        "client_for",
        lambda context, model, role, client=None: providers.client_for(
            context, model, role, client=FakeCompletion()
        ),
    )
    worker = Worker(db)
    worker.start()
    try:
        with db.connect() as conn:
            jobs_store.insert(
                conn, "bj", None, TREE, "brief", serialize_scope({}), "t"
            )
        deadline = time.monotonic() + 5
        row = None
        while time.monotonic() < deadline:
            with db.connect() as conn:
                row = conn.execute(
                    "SELECT status FROM jobs WHERE id='bj'"
                ).fetchone()
            if row["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.02)
    finally:
        worker.stop()
        worker.join(timeout=5)  # let the claim query finish before we read
    assert row is not None and row["status"] == "succeeded"
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM briefs").fetchone()[0] == 2


NON_ANSWER = (
    "This appears to be a set of files rather than a request. Are you sharing "
    "them so that I can summarise them for you, or did you want something "
    "else entirely here?"
)


def test_a_non_answer_is_retried_and_the_good_retry_is_stored(
    db: Database,
) -> None:
    class Talkback:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, request: CompletionRequest) -> CompletionResult:
            self.calls += 1
            text = (
                NON_ANSWER
                if self.calls % 2
                else "A proper brief body describing the topic now."
            )
            return CompletionResult(text, Usage(40, 12))

    client = Talkback()
    brief(job(), JobContext(db), client=client)
    assert client.calls == 4  # two nodes, each one retry
    with db.connect() as conn:
        for node_id in _node_ids(db):
            row = briefs.get(conn, node_id)
            assert row is not None
            assert row["flagged"] == ""
            assert "A proper brief body describing" in row["text"]
            assert row["input_tokens"] == 80  # both calls are what it cost


def test_a_persistent_non_answer_is_stored_flagged_not_dropped(
    db: Database,
) -> None:
    client = FakeCompletion(text=NON_ANSWER)
    brief(job(), JobContext(db), client=client)
    assert client.calls == 4  # one retry per node, then it gives up
    with db.connect() as conn:
        for node_id in _node_ids(db):
            row = briefs.get(conn, node_id)
            assert row is not None  # the topic keeps a brief
            assert row["flagged"] == "asks-the-caller"
            assert NON_ANSWER in row["text"]


def test_a_good_brief_is_never_flagged_or_retried(db: Database) -> None:
    client = FakeCompletion()
    brief(job(), JobContext(db), client=client)
    assert client.calls == 2  # no retry
    with db.connect() as conn:
        for node_id in _node_ids(db):
            row = briefs.get(conn, node_id)
            assert row is not None
            assert row["flagged"] == ""


def test_a_brief_never_cites_a_section_it_did_not_read(db: Database) -> None:
    # the reduce input and the reference list must agree: a member with no
    # condensation that is dropped from the LLM input must not be cited. An
    # incomplete map is a gap; a map that cites a source it never read is an
    # error, and citations are the one thing we tell agents is mechanical.
    with db.connect() as conn, conn:
        orphan = add_condensed_section(conn, "uncondensed.py", b"zzz\n", 8)
        conn.execute(
            "DELETE FROM condensations WHERE content_hash = "
            "(SELECT content_hash FROM sections WHERE id = ?)",
            (orphan,),
        )
        node = conn.execute(
            "SELECT id FROM nodes WHERE tree = ? AND level = 0 ORDER BY id",
            (TREE,),
        ).fetchone()["id"]
        cluster_store.add_member(
            conn, int(node), orphan, forced=False, similarity=None
        )

    brief(job(), JobContext(db), client=FakeCompletion(text="BODY " * 12))

    with db.connect() as conn:
        row = briefs.get(conn, int(node))
        inputs = briefs.reduce_input(conn, int(node), MODEL)
    cited = json.loads(row["members"])
    assert inputs.dropped == 1
    assert not any("uncondensed.py" in uri for uri in cited)
    assert list(inputs.uris) == cited  # the two halves agree, by construction
    assert "no condensation" in row["flagged"]  # and the gap is not silent


def test_brief_reduces_what_the_condense_model_wrote(db: Database) -> None:
    # condensations are keyed by the model that wrote them: with a cheap
    # condense model and a smart brief model, `brief` must still find the
    # condensations. Reading them under its OWN name finds none and briefs
    # nothing — silently, because an empty reduce input is not an error
    # anywhere.
    with db.connect() as conn, conn:
        conn.execute("DELETE FROM registry WHERE collection = 'models'")
        for name, role in (("cheap", "condense"), ("smart", "brief")):
            registry_store.insert(
                conn,
                "models",
                name,
                json.dumps(
                    {
                        "name": name,
                        "kind": "text",
                        "connection": "c",
                        "model": name,
                        "role": role,
                    }
                ),
                None,
                "t",
            )
        # the condensations exist under the CHEAP model, as condense wrote them
        conn.execute(
            "UPDATE condensations SET model_name = 'cheap' "
            "WHERE model_name = ?",
            (MODEL,),
        )

    client = FakeCompletion(text="BODY " * 12)
    brief(job(), JobContext(db), client=client)

    assert client.contents  # it had something to reduce
    joined = "\n".join(client.contents)
    assert "condensation of a.py" in joined
    with db.connect() as conn:
        assert briefs.get(conn, _node_ids(db)[0]) is not None


def test_the_run_reports_the_tokens_it_spent(db: Database) -> None:
    # the job tests plant this result by hand, so only
    # calling the OP proves anything about the op that writes it.
    outcome = brief(job(), JobContext(db), client=FakeCompletion())

    assert outcome["tokens"] == {"input": 80, "output": 24}  # two nodes


def test_the_nodes_are_briefed_concurrently(db: Database) -> None:
    # one node's reduce tells another's nothing, so a brief pass must not be
    # serial either. `Paired` answers only in twos and times out if it is alone.
    client = Paired()

    outcome = brief(job(), JobContext(db), client=client)

    assert client.peak >= 2
    assert outcome["briefed"] == 2
    with db.connect() as conn:
        assert all(
            briefs.get(conn, node_id) is not None for node_id in _node_ids(db)
        )


def test_text_above_the_title_is_dropped(db: Database) -> None:
    client = FakeCompletion(
        "Still researching: the lookups are done.\n\n"
        "# entity-emailer: queue worker\n\nThe brief body describes it."
    )
    brief(job(), JobContext(db), client=client)
    with db.connect() as conn:
        for node_id in _node_ids(db):
            row = briefs.get(conn, node_id)
            assert row is not None
            assert row["text"].startswith("# entity-emailer: queue worker")
