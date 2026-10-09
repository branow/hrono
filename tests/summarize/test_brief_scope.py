"""A job scoped to ONE topic rewrites that topic and no other.

The control is the unscoped run over the same two stale topics: it rewrites
both, so the scoped run's single rewrite is the scope and not a gate that
happened to hold the other back.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster import store as cluster_store
from hrono.db.database import Database
from hrono.jobs.ops import JobContext
from hrono.summarize import briefs
from hrono.summarize.brief import brief
from hrono.summarize.brief_upper import brief_upper
from tests.summarize import test_brief_upper as upper
from tests.summarize.test_brief import (
    FakeCompletion,
    add_condensed_section,
    job,
    register_brief_prompt,
    register_text_model,
)

TREE = "default"
FIRST = "The first summary describes what this topic contains."
NEW = "A newer summary describing the very same topic again."


@pytest.fixture
def db(tmp_path: object) -> Iterator[tuple[Database, int, int]]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register_text_model(conn)
        register_brief_prompt(conn)
        first = add_condensed_section(conn, "a.py", b"aaa\n", 0)
        second = add_condensed_section(conn, "b.py", b"bbb\n", 1)
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [(0, first, False, None), (1, second, False, None)],
            [(first, [0.1]), (second, [0.2])],
        )
        nodes = [
            int(r["id"])
            for r in conn.execute("SELECT id FROM nodes ORDER BY id")
        ]
    brief(job(), JobContext(database), client=FakeCompletion(FIRST))
    with database.write() as conn:
        for node in nodes:
            briefs.mark_stale(conn, node)
    yield database, nodes[0], nodes[1]
    database.close()


def _text(database: Database, node_id: int) -> str:
    with database.connect() as conn:
        row = briefs.get(conn, node_id)
    assert row is not None
    return str(row["text"])


def test_an_unscoped_run_rewrites_every_stale_topic(
    db: tuple[Database, int, int],
) -> None:
    database, one, two = db
    client = FakeCompletion(NEW)

    brief(job(), JobContext(database), client=client)

    assert (_text(database, one), _text(database, two)) == (NEW, NEW)
    assert client.calls == 2


def test_a_scoped_run_rewrites_only_the_topic_it_names(
    db: tuple[Database, int, int],
) -> None:
    database, one, two = db
    client = FakeCompletion(NEW)

    outcome = brief(job({"node": two}), JobContext(database), client=client)

    assert _text(database, two) == NEW
    assert _text(database, one) == FIRST
    assert client.calls == 1
    assert outcome["briefed"] == 1
    with database.connect() as conn:
        left = briefs.get(conn, one)
    assert left is not None and left["stale"] == 1


def test_a_scope_naming_no_stale_topic_calls_nothing(
    db: tuple[Database, int, int],
) -> None:
    database, one, _ = db
    with database.write() as conn:
        conn.execute("UPDATE briefs SET stale = 0 WHERE node_id = ?", (one,))
        conn.execute(
            "UPDATE briefs SET member_signature = ?, prompt_hash = ?, "
            "model_name = ? WHERE node_id = ?",
            (
                briefs.member_signature(conn, one),
                *_current(conn, one),
                one,
            ),
        )
    client = FakeCompletion(NEW)

    outcome = brief(job({"node": one}), JobContext(database), client=client)

    assert client.calls == 0
    assert outcome["briefed"] == 0


def _current(conn: object, node_id: int) -> tuple[str, str]:
    from hrono.summarize.resolve import (
        resolve_prompt,
        resolve_text_model,
        template_hash,
    )

    model = resolve_text_model(conn, {}, "brief")  # type: ignore[arg-type]
    _, template = resolve_prompt(conn, "brief")  # type: ignore[arg-type]
    return template_hash(template), str(model["name"])


@pytest.fixture
def parents(tmp_path: Path) -> Iterator[tuple[Database, list[int]]]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        upper.register(conn)
        a = upper.leaf_node(conn, 0, "child brief A about widgets")
        b = upper.leaf_node(conn, 0, "child brief B about gadgets")
        c = upper.leaf_node(conn, 1, "child brief C about pipelines")
        d = upper.leaf_node(conn, 1, "child brief D about queues")
        cluster_store.replace_level(
            conn,
            TREE,
            1,
            [
                (0, a, False, None),
                (0, b, False, None),
                (1, c, False, None),
                (1, d, False, None),
            ],
        )
        ids = [
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM nodes WHERE level = 1 ORDER BY id"
            )
        ]
    yield database, ids
    database.close()


def test_an_upper_run_scoped_to_one_parent_writes_only_that_parent(
    parents: tuple[Database, list[int]],
) -> None:
    database, ids = parents
    client = upper.FakeCompletion()

    brief_upper(
        dataclasses.replace(upper.job(), scope={"level": 1, "node": ids[1]}),
        JobContext(database),
        client=client,
    )

    with database.connect() as conn:
        written = [briefs.get(conn, node) is not None for node in ids]
    assert written == [False, True]
    assert client.calls == 1
