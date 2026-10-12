"""The gate: recall answers only a question the tree has the words for."""

from collections.abc import Iterator

import pytest

from hrono.db.database import Database
from hrono.recall import gate
from tests.recall.test_engine import add_passage, unit


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        add_passage(conn, b"payment account lock applied after NSF\n", unit(0))
        add_passage(
            conn,
            b"invoice statement for the account\n",
            unit(1),
            "other.py",
            source="elsewhere",
        )
    yield database
    database.close()


def test_content_words_skip_function_words_and_short_tokens() -> None:
    assert gate.words("How is the account locked, and by what?") == (
        "account",
        "locked",
    )


def test_coverage_is_the_share_of_words_the_tree_has(db: Database) -> None:
    with db.connect() as conn:
        # payment, account, lock occur; sourdough does not
        assert gate.coverage(conn, "payment account lock sourdough") == 0.75


def test_a_question_at_the_bar_is_answered(db: Database) -> None:
    with db.connect() as conn:
        assert gate.answers(conn, "When is a payment account lock applied?")
        assert not gate.answers(conn, "How do I knit a cable stitch?")


def test_words_count_only_inside_the_scope(db: Database) -> None:
    with db.connect() as conn:
        ids = conn.execute(
            "SELECT id FROM passages WHERE source = 'repo'"
        ).fetchall()
        scope = frozenset(int(row[0]) for row in ids)
        # "invoice" and "statement" occur only in the other source
        assert gate.coverage(conn, "invoice statement", scope) == 0.0
        assert gate.coverage(conn, "invoice statement") == 1.0


def test_a_word_is_found_in_another_form(db: Database) -> None:
    assert gate.stem("issued") == "issu"
    assert gate.stem("rules") == "rule"
    assert gate.stem("locking") == "lock"
    with db.connect() as conn:
        assert gate.coverage(conn, "locked payments") == 1.0
