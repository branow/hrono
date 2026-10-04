"""#431: the `brief-preview` op writes what an unsaved prompt would, and keeps
nothing of it.

The guard that matters is the negative one, so every test that runs the op
compares the whole tree and registry before and after, not one table: a
preview that stored its reply, or saved its template, is the defect.
"""

import json
from collections.abc import Iterator

import pytest

from hrono.cluster import store as cluster_store
from hrono.db.database import Database
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.jobs.worker import enqueue
from hrono.llm.client import LLMError
from hrono.summarize import briefs
from hrono.summarize.brief_preview import brief_preview
from hrono.usage.rollup import for_jobs
from tests.summarize.test_brief import (
    MODEL,
    TREE,
    FakeCompletion,
    add_condensed_section,
    register_brief_prompt,
    register_text_model,
)

DRAFT = "Rewrite tersely: {content}"


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")  # type: ignore[operator]
    with database.connect() as conn, conn:
        register_text_model(conn)
        register_brief_prompt(conn)
        a = add_condensed_section(conn, "a.py", b"aaa\n", 0)
        b = add_condensed_section(conn, "b.py", b"bbb\n", 1)
        c = add_condensed_section(conn, "c.py", b"ccc\n", 2)
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [(0, a, False, None), (0, b, False, None), (1, c, False, None)],
            [(a, [0.1]), (b, [0.1]), (c, [0.2])],
        )
        for node in _ids(conn, 0):
            briefs.upsert(
                conn,
                node,
                f"the current brief of {node}",
                model_name=MODEL,
                prompt_name="brief",
                prompt_hash="h",
                member_signature="sig",
                input_tokens=1,
                output_tokens=1,
            )
    yield database
    database.close()


def _ids(conn: object, level: int) -> list[int]:
    rows = conn.execute(  # type: ignore[attr-defined]
        "SELECT id FROM nodes WHERE level = ? ORDER BY id", (level,)
    ).fetchall()
    return [int(row["id"]) for row in rows]


def job(node: int, role: str = "brief", template: str = DRAFT) -> Job:
    return Job(
        id="p1",
        parent_id=None,
        tree=TREE,
        op="brief-preview",
        scope={"node": node, "role": role, "template": template},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


def snapshot(database: Database) -> dict[str, list[tuple[object, ...]]]:
    with database.connect() as conn:
        return {
            table: [
                tuple(row)
                for row in conn.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608
            ]
            for table in ("nodes", "node_members", "briefs", "registry")
        }


def test_it_is_registered() -> None:
    assert "brief-preview" in OPS


def test_it_writes_the_reply_under_the_unsaved_template(db: Database) -> None:
    with db.connect() as conn:
        node = _ids(conn, 0)[0]
    client = FakeCompletion()

    outcome = brief_preview(job(node), JobContext(db), client=client)

    assert (
        outcome["text"] == "The brief body describes what this topic contains."
    )
    assert client.calls == 1
    assert client.contents[0].startswith("Rewrite tersely:")
    assert "Brief this group" not in client.contents[0]
    assert "condensation of a.py" in client.contents[0]
    assert outcome["tokens"] == {"input": 40, "output": 12}


def test_the_tree_and_the_registry_are_untouched(db: Database) -> None:
    with db.connect() as conn:
        node = _ids(conn, 0)[0]
    before = snapshot(db)

    brief_preview(job(node), JobContext(db), client=FakeCompletion())

    assert snapshot(db) == before


def test_an_upper_topic_is_previewed_from_its_child_briefs(
    db: Database,
) -> None:
    with db.connect() as conn, conn:
        children = _ids(conn, 0)
        cluster_store.replace_level(
            conn, TREE, 1, [(0, children[0], False, None)]
        )
        parent = _ids(conn, 1)[0]
        briefs.upsert(
            conn,
            parent,
            "an upper brief",
            model_name=MODEL,
            prompt_name="brief-upper",
            prompt_hash="h",
            member_signature="sig",
            input_tokens=1,
            output_tokens=1,
        )
    client = FakeCompletion()

    brief_preview(job(parent, "brief-upper"), JobContext(db), client=client)

    assert f"the current brief of {children[0]}" in client.contents[0]


@pytest.mark.parametrize(
    ("role", "level"), [("brief", 1), ("brief-upper", 0)], ids=["up", "down"]
)
def test_a_role_that_does_not_write_for_the_level_says_so(
    db: Database, role: str, level: int
) -> None:
    with db.connect() as conn, conn:
        child = _ids(conn, 0)[0]
        cluster_store.replace_level(conn, TREE, 1, [(0, child, False, None)])
        node = _ids(conn, level)[0]

    with pytest.raises(LLMError, match=f"does not write for a level {level}"):
        brief_preview(job(node, role), JobContext(db), client=FakeCompletion())


@pytest.mark.parametrize(
    ("scope", "says"),
    [
        ({"role": "brief", "template": DRAFT}, "needs a topic"),
        ({"node": 1, "role": "judge", "template": DRAFT}, "needs a topic"),
        ({"node": 1, "role": "brief", "template": "no token"}, "must contain"),
        ({"node": 9999, "role": "brief", "template": DRAFT}, "topic not found"),
    ],
    ids=["no-topic", "judge", "no-placeholder", "unknown-topic"],
)
def test_a_preview_that_cannot_run_fails_and_calls_nothing(
    db: Database, scope: dict[str, object], says: str
) -> None:
    client = FakeCompletion()
    request = Job(**{**job(1).__dict__, "scope": scope})

    with pytest.raises(LLMError, match=says):
        brief_preview(request, JobContext(db), client=client)

    assert client.calls == 0


def test_a_topic_with_nothing_to_brief_from_says_so(db: Database) -> None:
    with db.connect() as conn, conn:
        node = _ids(conn, 0)[0]
        conn.execute("DELETE FROM condensations")

    with pytest.raises(LLMError, match="nothing to write a brief from"):
        brief_preview(job(node), JobContext(db), client=FakeCompletion())


def test_its_calls_are_recorded_against_the_job(db: Database) -> None:
    with db.connect() as conn:
        node = _ids(conn, 0)[0]
    job_id = enqueue(
        db,
        "brief-preview",
        {"node": node, "role": "brief", "template": DRAFT},
        tree=TREE,
    )

    brief_preview(
        job(node), JobContext(db, job_id=job_id), client=FakeCompletion()
    )

    with db.connect() as conn:
        spent = for_jobs(conn, job_id)
    assert spent is not None and spent["calls"] == 1
    assert json.dumps(spent["tokens"])
