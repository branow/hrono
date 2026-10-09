"""Split and the diff read UNITS, not files.

The seam's whole claim is that a source type is a table entry. These drive the
ops over a reader that has no filesystem behind it at all — its units are held
in memory, as a wiki's would be behind an API — and check that what comes out
still obeys hrono's identity rules: the URI scheme, and a section that
reassembles byte-identically from its passages.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.db.database import Database
from hrono.ingest import store
from hrono.ingest.diff import diff
from hrono.ingest.readers import READERS, Reader, Unit
from hrono.ingest.split_op import SplitError, split_source
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.registry import store as registry_store

SITE = "example.atlassian.net/wiki"
PAGES = {
    "spaces/ENG/onboarding.md": (
        b"# Onboarding\n\nRead this first. It explains how the team works,\n"
        b"who to ask, and what to install before day one.\n"
    ),
    "spaces/ENG/deploys.md": (
        b"# Deploys\n\nA deploy is a tag plus a button. The button is in the\n"
        b"release tool; the tag is cut from main.\n"
    ),
}


def _job(name: str) -> Job:
    return Job(
        id="j1",
        parent_id=None,
        tree=None,
        op="split",
        scope={"name": name},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture
def wiki(tmp_path: Path) -> Iterator[tuple[Database, JobContext, dict]]:
    """A source type with no files behind it: units come from memory."""
    pages = dict(PAGES)

    def units(config: dict[str, object], cache: Path) -> Iterator[Unit]:
        for path, body in sorted(pages.items()):
            yield Unit(path, body)

    def unit(config: dict[str, object], cache: Path, path: str) -> Unit:
        return Unit(path, pages[path])

    READERS["wiki"] = Reader(
        lambda config, cache: str(config["site"]), units, unit
    )
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn:
        registry_store.insert(
            conn,
            "sources",
            "docs",
            json.dumps({"name": "docs", "type": "wiki", "site": SITE}),
            None,
            "t",
        )
        with conn:
            conn.execute(
                "INSERT INTO source_state (source, version, synced_at) "
                "VALUES ('docs', 'v9', 't')"
            )
    try:
        yield database, JobContext(database, None, tmp_path / "cache"), pages
    finally:
        del READERS["wiki"]
        database.close()


def _sections(database: Database) -> list[tuple[str, str, str]]:
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT uri, path, source_type FROM sections WHERE source = 'docs'"
            " ORDER BY path, ordinal"
        ).fetchall()
    return [
        (str(r["uri"]), str(r["path"]), str(r["source_type"])) for r in rows
    ]


def test_split_ingests_a_source_with_no_files_behind_it(
    wiki: tuple[Database, JobContext, dict],
) -> None:
    database, context, _pages = wiki

    split_source(_job("docs"), context)

    stored = _sections(database)
    assert [path for _uri, path, _type in stored] == sorted(PAGES)
    # the URI scheme is the reader's to fill, not git's to own
    for uri, path, source_type in stored:
        assert source_type == "wiki"
        assert uri == f"wiki://{SITE}/{path}@v9"

    with database.connect() as conn:
        passages = [
            str(row["uri"])
            for row in conn.execute(
                "SELECT uri FROM passages WHERE source = 'docs' "
                "ORDER BY section_id, ordinal"
            ).fetchall()
        ]
    # a passage addresses the same resource as its section — position is data,
    # not identity. (The spec's `#chunk-n` fragment is not emitted by any
    # source type.)
    assert passages
    assert all(u.startswith(f"wiki://{SITE}/spaces/ENG/") for u in passages)


def test_a_section_still_reassembles_from_its_passages(
    wiki: tuple[Database, JobContext, dict],
) -> None:
    # the tiling rule holds whatever the source is: the passages of a section
    # tile its bytes exactly, which is what lets recall inject a passage and the
    # tree reason over a section.
    database, context, _pages = wiki

    split_source(_job("docs"), context)

    with database.connect() as conn:
        for row in conn.execute(
            "SELECT id, content_hash FROM sections WHERE source = 'docs'"
        ).fetchall():
            section = store.get_content(conn, str(row["content_hash"]))
            passages = conn.execute(
                "SELECT content_hash FROM passages WHERE section_id = ? "
                "ORDER BY ordinal",
                (row["id"],),
            ).fetchall()
            tiled = b"".join(
                store.get_content(conn, str(p["content_hash"]))
                for p in passages
            )
            assert tiled == section


def test_the_diff_asks_the_reader_what_the_source_holds_now(
    wiki: tuple[Database, JobContext, dict],
) -> None:
    database, context, pages = wiki
    split_source(_job("docs"), context)

    pages["spaces/ENG/deploys.md"] = b"# Deploys\n\nThe button moved.\n"
    pages["spaces/ENG/oncall.md"] = b"# On call\n\nOne week, then hand over.\n"
    del pages["spaces/ENG/onboarding.md"]

    with database.connect() as conn:
        changes = diff(
            conn,
            "docs",
            READERS["wiki"],
            {"site": SITE},
            context.cache_for("docs"),
        )

    assert {(c.path, c.status) for c in changes} == {
        ("spaces/ENG/deploys.md", "changed"),
        ("spaces/ENG/oncall.md", "new"),
        ("spaces/ENG/onboarding.md", "deleted"),
    }


def test_a_type_with_no_reader_fails_by_name(
    wiki: tuple[Database, JobContext, dict],
) -> None:
    database, context, _pages = wiki
    with database.connect() as conn, conn:
        conn.execute(
            "UPDATE registry SET config = ? WHERE name = 'docs'",
            # an unregistered type on purpose: a type named here could become
            # real, as `notion` did.
            (json.dumps({"name": "docs", "type": "sharepoint"}),),
        )

    with pytest.raises(SplitError) as raised:
        split_source(_job("docs"), context)

    assert "sharepoint" in str(raised.value)
