"""E033: an overwritten brief is kept, five deep, with who and why."""

from __future__ import annotations

from pathlib import Path

import pytest

from hrono import edits
from hrono.cluster import store as cluster_store
from hrono.db.database import open_database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.summarize import briefs

TREE = "default"


@pytest.fixture
def world(tmp_path: Path):  # type: ignore[no-untyped-def]
    conn = open_database(tmp_path / "hrono.db")
    body = b"a chunk\n"
    istore.upsert_content(conn, content_hash(body), body)
    with conn:
        section = istore.insert_section(
            conn,
            source="docs",
            address=Address("git", "ex/docs", "a.md", "v1"),
            start=0,
            end=len(body),
            content_hash=content_hash(body),
            ordinal=0,
        )
        node = cluster_store.add_leaf_node(conn, TREE, [(section, False, None)])
    yield conn, node
    conn.close()


def _write(conn, node: int, text: str, model: str = "m") -> None:  # type: ignore[no-untyped-def]
    with conn:
        briefs.upsert(
            conn,
            node,
            text,
            model_name=model,
            prompt_name="brief",
            prompt_hash="h",
            member_signature="sig",
            input_tokens=1,
            output_tokens=1,
        )


def test_a_first_write_keeps_nothing(world) -> None:  # type: ignore[no-untyped-def]
    conn, node = world

    _write(conn, node, "first")

    assert briefs.versions(conn, node) == []


def test_a_regeneration_keeps_the_text_it_replaced(world) -> None:  # type: ignore[no-untyped-def]
    conn, node = world
    _write(conn, node, "first", model="old-model")

    _write(conn, node, "second")

    (kept,) = briefs.versions(conn, node)
    assert (kept["text"], kept["model_name"], kept["reason"]) == (
        "first",
        "old-model",
        "regen",
    )


def test_a_hand_rewrite_keeps_the_text_it_replaced(world) -> None:  # type: ignore[no-untyped-def]
    conn, node = world
    _write(conn, node, "first")

    with conn:
        edits.override_brief(conn, TREE, node, "by a person")
    _write(conn, node, "regenerated")

    newest, older = briefs.versions(conn, node)
    assert (newest["text"], newest["model_name"], newest["reason"]) == (
        "by a person",
        "hand-edited",
        "regen",
    )
    assert (older["text"], older["reason"]) == ("first", "rewrite")


def test_only_the_newest_five_are_kept(world) -> None:  # type: ignore[no-untyped-def]
    conn, node = world

    for number in range(7):
        _write(conn, node, f"text {number}")

    kept = [row["text"] for row in briefs.versions(conn, node)]
    assert kept == [f"text {n}" for n in (5, 4, 3, 2, 1)]
    assert str(briefs.get(conn, node)["text"]) == "text 6"
