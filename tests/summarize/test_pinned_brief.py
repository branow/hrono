"""A pinned brief is the operator's, and the pipeline leaves it alone.

The spec's whole reason for pins: "Without this, a manual fix gets silently
reverted on the next update." So the test that matters is not "the pin is
stored" — it is a REAL `brief` run over a node whose brief is stale, next to an
unstale sibling, proving the pin is what stopped it.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from hrono import pins
from hrono.cluster import store as cluster_store
from hrono.db.database import Database
from hrono.jobs.ops import JobContext
from hrono.summarize import briefs
from hrono.summarize.brief import brief
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
    yield database, nodes[0], nodes[1]
    database.close()


def _text(database: Database, node_id: int) -> str | None:
    with database.connect() as conn:
        row = briefs.get(conn, node_id)
    return None if row is None else str(row["text"])


def _signature(database: Database, node_id: int) -> str | None:
    with database.connect() as conn:
        row = briefs.get(conn, node_id)
    return None if row is None else str(row["member_signature"])


def test_a_pinned_brief_survives_a_run_that_would_rewrite_it(
    db: tuple[Database, int, int],
) -> None:
    database, held, free = db
    context = JobContext(database)
    brief(job(), context, client=FakeCompletion(FIRST))
    before = _signature(database, held)

    with database.write() as conn:
        pins.pin(conn, pins.BRIEF, held, reason="the model kept missing it")
        # stale the REAL way — each node gains a member — so the STORED
        # signature is untouched and "was it re-signed" means something.
        extra = add_condensed_section(conn, "c.py", b"ccc\n", 2)
        for node_id in (held, free):
            cluster_store.add_member(
                conn, node_id, extra, forced=False, similarity=None
            )

    outcome = brief(job(), context, client=FakeCompletion(NEW))

    assert _text(database, held) == FIRST  # untouched
    assert _signature(database, held) == before  # and not re-signed
    assert _text(database, free) == NEW  # the sibling moved
    assert outcome["skipped_pinned"] == 1
    assert outcome["briefed"] == 1


def test_unpinning_hands_it_back(db: tuple[Database, int, int]) -> None:
    database, held, _free = db
    context = JobContext(database)
    brief(job(), context, client=FakeCompletion(FIRST))
    with database.write() as conn:
        pins.pin(conn, pins.BRIEF, held)
        conn.execute(
            "UPDATE briefs SET member_signature = 'stale' WHERE node_id = ?",
            (held,),
        )

    brief(job(), context, client=FakeCompletion(NEW))
    assert _text(database, held) == FIRST

    with database.write() as conn:
        assert pins.unpin(conn, pins.BRIEF, held) is True

    brief(job(), context, client=FakeCompletion(NEW))
    assert _text(database, held) == NEW


def test_a_pin_makes_no_llm_call_at_all(
    db: tuple[Database, int, int],
) -> None:
    # held back at SELECTION, so a pinned node costs nothing — the point of
    # doing it there rather than discarding the answer afterwards.
    database, held, free = db
    context = JobContext(database)
    with database.write() as conn:
        pins.pin(conn, pins.BRIEF, held)

    # the default text passes the shape gate; a reply that fails it is retried
    # once, which would make the call count say nothing about pins.
    completion = FakeCompletion()
    brief(job(), context, client=completion)

    assert completion.calls == 1  # the free node only
    assert _text(database, held) is None


def test_a_retired_node_takes_its_pins_with_it(
    db: tuple[Database, int, int],
) -> None:
    database, held, _free = db
    with database.write() as conn:
        pins.pin(conn, pins.BRIEF, held)
        pins.pin(conn, pins.PARENTING, held)
        cluster_store.delete_node(conn, held)

    with database.connect() as conn:
        assert pins.reasons(conn, held) == {}
        assert pins.pinned(conn, pins.BRIEF) == frozenset()


def test_a_deleted_section_takes_its_membership_pin(
    db: tuple[Database, int, int],
) -> None:
    database, held, _free = db
    with database.connect() as conn:
        section = int(
            conn.execute("SELECT id FROM sections ORDER BY id").fetchone()["id"]
        )
    with database.write() as conn:
        pins.pin(conn, pins.MEMBERSHIP, section)
        conn.execute("DELETE FROM sections WHERE id = ?", (section,))

    with database.connect() as conn:
        assert pins.is_pinned(conn, pins.MEMBERSHIP, section) is False


def test_an_unknown_kind_is_refused(db: tuple[Database, int, int]) -> None:
    # the kinds are a closed vocabulary: a typo must not create a pin nothing
    # will ever read.
    database, held, _free = db
    with database.write() as conn, pytest.raises(ValueError, match="unknown"):
        pins.pin(conn, "membrship", held)


def test_a_pin_records_why_it_is_held(db: tuple[Database, int, int]) -> None:
    database, held, _free = db
    with database.write() as conn:
        pins.pin(conn, pins.BRIEF, held, reason="hand-written for the audit")

    with database.connect() as conn:
        assert pins.reasons(conn, held) == {
            "brief": "hand-written for the audit"
        }
