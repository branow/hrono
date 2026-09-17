"""#102's data step: the member footer moves out of the brief text."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.db.backfill import brief_members
from hrono.db.database import Database

LEAF = (
    "This topic covers the signing helpers and how they fit together."
    "\n\nReferences:\n- git://ex/repo/a.py@v1\n- git://ex/repo/b.py@v1\n"
)
UPPER = "The branch over signing.\n\nChildren:\n- node 3\n- node 4\n"
PROSE = (
    "The package documents its own references. **References:** are listed in"
    " the readme, which is not a machine footer at all."
)


def _brief(conn: object, node_id: int, text: str) -> None:
    conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO nodes(id, tree, level, label, created_at) "
        "VALUES (?, 'default', 0, 0, 't')",
        (node_id,),
    )
    conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO briefs(node_id, text, model_name, prompt_name, "
        "prompt_hash, member_signature, input_tokens, output_tokens, "
        "created_at) VALUES (?, ?, 'm', 'brief', 'h', 'sig', 1, 1, 't')",
        (node_id, text),
    )


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        _brief(conn, 1, LEAF)
        _brief(conn, 2, UPPER)
        _brief(conn, 3, PROSE)
    yield database
    database.close()


def _row(db: Database, node_id: int) -> tuple[str, list[str]]:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT text, members FROM briefs WHERE node_id = ?", (node_id,)
        ).fetchone()
    return row["text"], json.loads(row["members"])


def test_a_leaf_footer_moves_into_members(db: Database) -> None:
    with db.connect() as conn, conn:
        brief_members(conn)
    text, members = _row(db, 1)
    assert members == ["git://ex/repo/a.py@v1", "git://ex/repo/b.py@v1"]
    assert "References:" not in text
    assert text.endswith("how they fit together.")


def test_an_upper_children_list_moves_too(db: Database) -> None:
    with db.connect() as conn, conn:
        brief_members(conn)
    text, members = _row(db, 2)
    assert members == ["node 3", "node 4"]
    assert "Children:" not in text


def test_prose_that_merely_mentions_references_is_left_alone(
    db: Database,
) -> None:
    # the sentinel is the machine format, not the word: a brief that talks
    # about references keeps its text and gets no members.
    with db.connect() as conn, conn:
        brief_members(conn)
    text, members = _row(db, 3)
    assert text == PROSE
    assert members == []


def test_running_it_twice_changes_nothing(db: Database) -> None:
    with db.connect() as conn, conn:
        brief_members(conn)
    once = [_row(db, node) for node in (1, 2, 3)]
    with db.connect() as conn, conn:
        brief_members(conn)
    assert [_row(db, node) for node in (1, 2, 3)] == once


def test_a_retired_nodes_brief_passages_are_cleared(db: Database) -> None:
    # a node that no longer exists keeps no passages: they are summaries of a
    # topic the map does not hold, and they carried the old footers too.
    with db.connect() as conn, conn:
        conn.execute(
            "INSERT INTO contents(content_hash, body, byte_len, created_at) "
            "VALUES ('h', X'78', 1, 't')"
        )
        conn.execute(
            "INSERT INTO sections(source, source_type, instance, path, "
            "version, uri, byte_start, byte_end, content_hash, ordinal, "
            "created_at) VALUES ('node-99', 'node', 'hrono', 'x', 'v1', "
            "'node://x', 0, 1, 'h', 0, 't')"
        )
    with db.connect() as conn, conn:
        brief_members(conn)
    with db.connect() as conn:
        left = conn.execute(
            "SELECT COUNT(*) FROM sections WHERE source = 'node-99'"
        ).fetchone()[0]
    assert left == 0
