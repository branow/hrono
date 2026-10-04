"""E042: the recall log keeps what was asked, bounded per tree."""

from pathlib import Path

import pytest

from hrono.db.database import open_database
from hrono.recall import log
from hrono.recall.engine import Hit, Recall


def hit(score: float) -> Hit:
    return Hit("u", "source", "h", "b", score, 0, 1, None)


@pytest.fixture
def conn(tmp_path: Path):  # type: ignore[no-untyped-def]
    connection = open_database(tmp_path / "hrono.db")
    yield connection
    connection.close()


def rows(conn, tree: str = "t") -> list[tuple]:  # type: ignore[no-untyped-def]
    return [
        tuple(r)
        for r in conn.execute(
            "SELECT question, hits, top_score, confident FROM recall_log "
            "WHERE tree = ? ORDER BY id",
            (tree,),
        )
    ]


def test_an_answer_records_its_best_score_and_a_refusal_records_none(
    conn,  # type: ignore[no-untyped-def]
) -> None:
    log.record(conn, "t", "ana", Recall((hit(0.9), hit(0.5)), None), "q1")
    log.record(conn, "t", "ana", Recall((), "nothing"), "q2")

    assert rows(conn) == [("q1", 2, 0.9, 1), ("q2", 0, None, 0)]


def test_the_cap_holds_per_tree_and_a_question_is_cut(
    conn,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(log, "KEEP", 2)
    for n in range(4):
        log.record(conn, "t", "ana", Recall((), "m"), f"q{n}")
    log.record(conn, "other", "ana", Recall((), "m"), "x" * 900)

    assert [r[0] for r in rows(conn)] == ["q2", "q3"]
    assert len(rows(conn, "other")[0][0]) == log.QUESTION_CHARS


def test_per_day_and_latest_read_the_same_rows(conn) -> None:  # type: ignore[no-untyped-def]
    log.record(conn, "t", "ana", Recall((hit(1.0),), None), "a")
    log.record(conn, "t", "bo", Recall((), "m"), "b")

    (day,) = log.per_day(conn, "t")
    assert (day["calls"], day["unsure"]) == (2, 1)
    assert [q["question"] for q in log.latest(conn, "t", 10)] == ["b", "a"]
