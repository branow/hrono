"""#215: is the tree up to date with its sources.

The remote is a real repository that really moves; the only thing stood in for
is the clock, which is what the one-minute memory is measured against.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database, open_database
from hrono.registry import store as registry_store
from hrono.server.freshness import Heads, survey
from tests.server.repo import commit, head_of, make_repo

KEY = Fernet.generate_key()


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    yield Database.adopt(conn)
    conn.close()


def _source(database: Database, name: str, url: str, kind: str = "git") -> None:
    with database.connect() as conn:
        registry_store.insert(
            conn,
            "sources",
            name,
            json.dumps({"name": name, "type": kind, "url": url, "auth": None}),
            None,
            "t",
        )


def _read(database: Database, name: str, commit_: str) -> None:
    with database.connect() as conn:
        conn.execute(
            "INSERT INTO source_state (source, version, synced_at) "
            "VALUES (?, ?, '2026-10-03T10:00:00+00:00')",
            (name, commit_),
        )


def _states(database: Database) -> dict[str, str]:
    return {
        one.name: one.state
        for one in survey(database, None, Heads(fresh_for=0.0), "default")
    }


def test_a_source_read_at_the_remotes_commit_is_up_to_date(
    database: Database, tmp_path: Path
) -> None:
    repo = make_repo(tmp_path / "r")
    _source(database, "docs", str(repo))
    _read(database, "docs", head_of(repo))

    assert _states(database) == {"docs": "current"}


def test_a_source_the_remote_has_moved_past_is_behind(
    database: Database, tmp_path: Path
) -> None:
    repo = make_repo(tmp_path / "r")
    _source(database, "docs", str(repo))
    _read(database, "docs", head_of(repo))
    commit(repo, "two")

    assert _states(database) == {"docs": "behind"}


def test_each_source_is_judged_on_its_own(
    database: Database, tmp_path: Path
) -> None:
    old, new = make_repo(tmp_path / "old"), make_repo(tmp_path / "new")
    for name, repo in (("old", old), ("new", new)):
        _source(database, name, str(repo))
        _read(database, name, head_of(repo))
    commit(old, "two")

    assert _states(database) == {"old": "behind", "new": "current"}


def test_a_source_the_tree_does_not_ingest_is_not_its_to_be_behind_on(
    database: Database, tmp_path: Path
) -> None:
    mine, other = make_repo(tmp_path / "mine"), make_repo(tmp_path / "other")
    for name, repo in (("mine", mine), ("other", other)):
        _source(database, name, str(repo))
        _read(database, name, head_of(repo))
    with database.connect() as conn:
        registry_store.insert(
            conn,
            "trees",
            "default",
            json.dumps({"name": "default", "sources": ["mine"]}),
            None,
            "t",
        )
    commit(other, "two")

    assert _states(database) == {"mine": "current"}


def test_a_source_never_read_says_so_and_is_not_asked_about(
    database: Database, tmp_path: Path
) -> None:
    _source(database, "docs", str(make_repo(tmp_path / "r")))

    [one] = survey(database, None, Heads(fresh_for=0.0), "default")

    assert (one.state, one.read_at, one.commit) == ("unread", None, None)


def test_a_remote_that_cannot_be_reached_is_neither_current_nor_behind(
    database: Database, tmp_path: Path
) -> None:
    _source(database, "docs", str(tmp_path / "gone"))
    _read(database, "docs", "abc123")

    assert _states(database) == {"docs": "unreachable"}


def test_a_source_that_cannot_be_compared_says_when_it_was_read(
    database: Database,
) -> None:
    _source(database, "wiki", "https://example.invalid", kind="notion")
    _read(database, "wiki", "v7")

    [one] = survey(database, None, Heads(fresh_for=0.0), "default")

    assert (one.state, one.read_at, one.commit) == (
        "not-compared",
        "2026-10-03T10:00:00+00:00",
        "v7",
    )


def test_a_probe_that_raises_is_a_remote_that_is_not_known() -> None:
    def broken(config: dict[str, object], timeout: float) -> str | None:
        raise RuntimeError("boom")

    assert Heads(broken).read({"a": {"url": "x"}}) == {"a": None}


def test_the_remote_is_asked_once_a_minute_not_once_a_page_load() -> None:
    asked: list[str] = []
    now = [0.0]

    def probe(config: dict[str, object], timeout: float) -> str | None:
        asked.append(str(config["url"]))
        return "sha"

    heads = Heads(probe, fresh_for=60.0, clock=lambda: now[0])
    config = {"a": {"url": "u"}}

    heads.read(config)
    now[0] = 59.0
    heads.read(config)
    now[0] = 61.0
    heads.read(config)

    assert asked == ["u", "u"]


def test_a_changed_url_is_asked_again_at_once() -> None:
    asked: list[str] = []

    def probe(config: dict[str, object], timeout: float) -> str | None:
        asked.append(str(config["url"]))
        return "sha"

    heads = Heads(probe, fresh_for=60.0, clock=lambda: 0.0)
    heads.read({"a": {"url": "one"}})
    heads.read({"a": {"url": "two"}})

    assert asked == ["one", "two"]
