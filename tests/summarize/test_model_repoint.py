"""Repointing a model at another upstream model invalidates its briefs.

End to end through the `brief` op, not through the preview: the claim is that
the NEXT RUN rewrites exactly the briefs the repoint changed, and a preview
that agrees with a run that does nothing is two wrong answers agreeing.
"""

from __future__ import annotations

import json

from hrono.db.database import Database
from hrono.jobs.ops import JobContext
from hrono.registry import store as registry_store
from hrono.summarize.brief import brief
from tests.summarize.test_brief import (
    MODEL,
    TREE,
    FakeCompletion,
    job,
)
from tests.summarize.test_brief import (
    db as db,  # noqa: PLC0414 — the shared corpus fixture
)


def _repoint(database: Database, **changes: object) -> None:
    with database.connect() as conn, conn:
        config = json.loads(
            registry_store.get(conn, "models", MODEL)["config"]  # type: ignore[index]
        )
        registry_store.replace(
            conn,
            "models",
            MODEL,
            json.dumps({**config, **changes}),
            None,
            "t",
            None,
        )


def _fingerprints(database: Database) -> set[str | None]:
    with database.connect() as conn:
        return {
            row["model_fingerprint"]
            for row in conn.execute(
                "SELECT model_fingerprint FROM briefs"
            ).fetchall()
        }


def test_a_repoint_makes_the_briefs_stale_and_the_next_run_rewrites_them(
    db: Database,
) -> None:
    brief(job(), JobContext(db), client=FakeCompletion())
    before = _fingerprints(db)

    _repoint(db, model="claude-opus-5")
    second = FakeCompletion("A different model's words, at some length here.")
    result = brief(job(), JobContext(db), client=second)

    assert result["briefed"] == 2
    assert second.calls == 2
    assert _fingerprints(db) != before


def test_changing_the_params_counts_as_a_different_model(
    db: Database,
) -> None:
    # the same weights called differently are not the same words
    brief(job(), JobContext(db), client=FakeCompletion())

    _repoint(db, params={"temperature": 0.9})
    again = FakeCompletion("Warmer words about the very same group of files.")

    assert brief(job(), JobContext(db), client=again)["briefed"] == 2


def test_changing_the_connection_rewrites_nothing(db: Database) -> None:
    """A credential is not a voice: same model, same words, no work."""
    brief(job(), JobContext(db), client=FakeCompletion())

    _repoint(db, connection="a-different-account")
    again = FakeCompletion()

    assert brief(job(), JobContext(db), client=again)["briefed"] == 0
    assert again.calls == 0


def test_re_writing_the_same_config_rewrites_nothing(db: Database) -> None:
    brief(job(), JobContext(db), client=FakeCompletion())

    _repoint(db)
    again = FakeCompletion()

    assert brief(job(), JobContext(db), client=again)["briefed"] == 0


def test_a_brief_from_before_the_column_stays_fresh(db: Database) -> None:
    """NULL is unknown provenance, not staleness (`0034`).

    An upgrade must not bill every install for a full re-brief of a corpus
    that has not changed.
    """
    brief(job(), JobContext(db), client=FakeCompletion())
    with db.connect() as conn, conn:
        conn.execute("UPDATE briefs SET model_fingerprint = NULL")

    _repoint(db, model="claude-opus-5")
    again = FakeCompletion()

    assert brief(job(), JobContext(db), client=again)["briefed"] == 0
    assert again.calls == 0


def test_a_rewrite_fills_the_fingerprint_in(db: Database) -> None:
    # it becomes accurate as briefs are rewritten for reasons of their own
    brief(job(), JobContext(db), client=FakeCompletion())
    with db.connect() as conn, conn:
        conn.execute("UPDATE briefs SET model_fingerprint = NULL, stale = 1")

    brief(job(), JobContext(db), client=FakeCompletion("Rewritten words here."))

    assert None not in _fingerprints(db)


def test_the_fingerprint_is_not_the_registry_name(db: Database) -> None:
    """The hole this closes, stated as a test.

    Two models with different upstream targets must not fingerprint alike just
    because someone could give them the same name.
    """
    from hrono.summarize.resolve import model_fingerprint

    one = {"name": "same", "model": "claude-sonnet-5", "params": {}}
    two = {"name": "same", "model": "claude-opus-5", "params": {}}

    assert model_fingerprint(one) != model_fingerprint(two)


def test_the_connection_is_not_part_of_the_fingerprint(db: Database) -> None:
    from hrono.summarize.resolve import model_fingerprint

    one = {"name": "m", "model": "x", "params": {}, "connection": "a"}
    two = {"name": "m", "model": "x", "params": {}, "connection": "b"}

    assert model_fingerprint(one) == model_fingerprint(two)


def test_briefs_still_agree_with_the_preview(db: Database) -> None:
    """The count the dry run shows and the work the repoint causes agree.

    They come from `stale_or_missing`, so this is a guard on that staying
    true rather than on two implementations happening to agree today.
    """
    from hrono.registry import impact

    brief(job(), JobContext(db), client=FakeCompletion())
    with db.connect() as conn:
        config = json.loads(
            registry_store.get(conn, "models", MODEL)["config"]  # type: ignore[index]
        )
        preview = impact.preview(
            conn, "models", MODEL, {**config, "model": "claude-opus-5"}
        )
    predicted = sum(item.stale.nodes for item in preview if item.tree == TREE)

    _repoint(db, model="claude-opus-5")
    done = brief(job(), JobContext(db), client=FakeCompletion("New words go."))

    assert predicted == done["briefed"] == 2
