"""#210: Settings says what a build still lacks, before one is attempted.

Each case is the refusal the run itself would meet, because the checks ask the
same resolvers the stages ask — so the "complete" case matters as much as the
gaps: a page that cried wolf over a registry the build accepts would be
ignored.
"""

from __future__ import annotations

import gc
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.registry import completeness
from hrono.registry import store as registry_store
from hrono.registry.collections import COLLECTIONS
from hrono.registry.seeding import seed_defaults

KEY = Fernet.generate_key()


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    db = open_database(tmp_path / "hrono.db")
    record = reconcile(db, KEY)
    # the shipped prompts, seeded the way `hrono serve` seeds them
    seed_defaults(db, Cipher.from_key(KEY, record.key_id), COLLECTIONS)
    yield db
    db.close()


def _register(conn: sqlite3.Connection, collection: str, **config: object):  # type: ignore[no-untyped-def]
    registry_store.insert(
        conn, collection, str(config["name"]), json.dumps(config), None, "t"
    )


def _complete(conn: sqlite3.Connection) -> None:
    _register(conn, "sources", name="a", type="git", url="x", auth={})
    _register(conn, "connections", name="cc", provider="claude-code")
    _register(conn, "models", name="mini", kind="embedding", model="m")
    _register(
        conn, "models", name="sonnet", kind="text", connection="cc", model="s"
    )


def _said(conn: sqlite3.Connection) -> list[str]:
    return [gap.says for gap in completeness.gaps(conn)]


def test_a_complete_registry_has_no_gaps(conn: sqlite3.Connection) -> None:
    """One text model serves every role on a one-model install."""
    _complete(conn)

    assert completeness.gaps(conn) == ()


def test_an_empty_registry_names_everything_it_lacks(
    conn: sqlite3.Connection,
) -> None:
    said = _said(conn)

    assert "no source is registered to read" in said
    assert "embedding: no embedding model available" in said
    assert "role condense: no text model available" in said
    assert "role judge (needed by sync): no text model available" in said


def test_a_role_with_no_model_is_reported_as_missing(
    conn: sqlite3.Connection,
) -> None:
    """Two text models and only one has a role: every OTHER role has no
    model, which the run discovers only when it reaches that stage."""
    _complete(conn)
    _register(
        conn,
        "models",
        name="haiku",
        kind="text",
        connection="cc",
        model="h",
        role="condense",
    )

    gaps = completeness.gaps(conn)
    roles = [gap.says.split(":")[0] for gap in gaps]

    assert roles == [
        "role brief",
        "role brief-upper",
        "role judge (needed by sync)",
    ]
    assert {gap.section for gap in gaps} == {"models"}


def test_a_model_whose_connection_is_gone_is_reported(
    conn: sqlite3.Connection,
) -> None:
    _complete(conn)
    registry_store.delete(conn, "connections", "cc")

    assert _said(conn) == [
        "model sonnet calls through connection cc, which is not registered"
    ]


def test_a_role_with_no_prompt_is_reported(conn: sqlite3.Connection) -> None:
    _complete(conn)
    registry_store.delete(conn, "prompts", "judge")

    assert _said(conn) == [
        "role judge (needed by sync): no judge prompt configured"
    ]


def test_the_delete_copy_has_every_column_the_real_registry_has(
    conn: sqlite3.Connection,
) -> None:
    """A migration that adds a registry column must reach the copy.

    The copy used to restate the table by hand, so a ninth column would have
    left the delete preview reading a registry the real one no longer was.
    """
    _complete(conn)
    conn.execute("ALTER TABLE registry ADD COLUMN later TEXT")
    conn.execute("UPDATE registry SET later = 'kept'")

    copy = completeness._registry_without(conn, ("sources", "a"))
    try:
        real = [r["name"] for r in conn.execute("PRAGMA table_info(registry)")]
        theirs = [
            r["name"] for r in copy.execute("PRAGMA table_info(registry)")
        ]
        rows = copy.execute("SELECT collection, later FROM registry").fetchall()
    finally:
        copy.close()

    assert theirs == real
    assert "later" in theirs
    assert {r["later"] for r in rows} == {"kept"}
    assert "sources" not in {r["collection"] for r in rows}


def test_the_delete_preview_closes_its_copy(
    conn: sqlite3.Connection, recwarn: pytest.WarningsRecorder
) -> None:
    _complete(conn)

    completeness.gaps(conn, without=("connections", "cc"))
    gc.collect()

    assert not [w for w in recwarn if issubclass(w.category, ResourceWarning)]
