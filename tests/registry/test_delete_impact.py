"""#210: what deleting a registry row would strand, said before it goes.

Asserted against rows written the way production writes them — sections
through the ingest store, topics through the cluster store, briefs and
condensations through their own upserts — because the counts are only worth
showing if they are the rows the next run would redo. Two trees, so a count
that ignored the tree could not pass.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest

from hrono.cluster import store as cluster_store
from hrono.db.database import open_database
from hrono.embed import store as embed_store
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.registry import impact
from hrono.registry import store as registry_store
from hrono.summarize import briefs
from hrono.summarize import store as summary_store
from hrono.summarize.resolve import template_hash

TEMPLATE = "Brief this group: {content}"


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    db = open_database(tmp_path / "hrono.db")
    yield db
    db.close()


def _register(conn: sqlite3.Connection, collection: str, **config: object):  # type: ignore[no-untyped-def]
    registry_store.insert(
        conn, collection, str(config["name"]), json.dumps(config), None, "t"
    )


def _topic(conn: sqlite3.Connection, tree: str, source: str, path: str) -> int:
    body = f"{tree}/{source}/{path}\n".encode()
    digest = content_hash(body)
    istore.upsert_content(conn, digest, body)
    section = istore.insert_section(
        conn,
        source=source,
        address=Address("git", f"ex/{source}", path, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )
    return cluster_store.add_leaf_node(conn, tree, [(section, False, None)])


def _brief(
    conn: sqlite3.Connection, node: int, model: str, template: str
) -> None:
    briefs.upsert(
        conn,
        node,
        f"A summary of node {node}.",
        model_name=model,
        prompt_name="brief",
        prompt_hash=template_hash(template),
        member_signature=briefs.member_signature(conn, node),
        input_tokens=10,
        output_tokens=5,
    )


@pytest.fixture
def built(conn: sqlite3.Connection) -> sqlite3.Connection:
    """alpha maps source a (two topics), beta maps source b (one topic)."""
    _register(conn, "sources", name="a", type="git", url="x", auth={})
    _register(conn, "sources", name="b", type="git", url="y", auth={})
    _register(conn, "trees", name="alpha", sources=["a"])
    _register(conn, "trees", name="beta", sources=["b"])
    _register(conn, "connections", name="cc", provider="claude-code")
    _register(
        conn, "models", name="sonnet", kind="text", connection="cc", model="s"
    )
    _register(
        conn, "models", name="haiku", kind="text", connection="cc", model="h"
    )
    _register(conn, "prompts", name="mine", role="brief", template=TEMPLATE)
    with conn:
        for path in ("one.md", "two.md"):
            _brief(conn, _topic(conn, "alpha", "a", path), "sonnet", TEMPLATE)
        _brief(conn, _topic(conn, "beta", "b", "three.md"), "haiku", "other")
    return conn


def _by_tree(found: Iterable[impact.TreeImpact]) -> dict[str, object]:
    return {hit.tree: hit for hit in found}


def test_deleting_a_model_counts_the_briefs_it_wrote_per_tree(
    built: sqlite3.Connection,
) -> None:
    found = _by_tree(impact.of_delete(built, "models", "sonnet"))

    assert set(found) == {"alpha"}  # beta's brief was written by haiku
    alpha = found["alpha"]
    assert alpha.stale.nodes == 2 and alpha.stale.levels == (0,)  # type: ignore[attr-defined]
    assert alpha.ops == ("brief",)  # type: ignore[attr-defined]
    assert alpha.estimate.brief_calls == 2  # type: ignore[attr-defined]


def test_deleting_a_model_counts_what_is_stored_under_its_name(
    built: sqlite3.Connection,
) -> None:
    """Condensations and vectors are keyed by the model's name, so they are
    made again by whichever model the stage resolves to next."""
    digest = content_hash(b"alpha/a/one.md\n")
    with built:
        summary_store.upsert(built, digest, "haiku", "condensed", 1, 1)
        embed_store.upsert_vector(built, digest, "haiku", [0.1, 0.2])

    found = [hit for hit in impact.of_delete(built, "models", "haiku")]
    stored = {hit.ops: hit.stale.sections for hit in found if hit.tree == "*"}

    assert stored == {("condense",): 1, ("embed",): 1}


def test_deleting_a_brief_prompt_counts_what_its_template_wrote(
    built: sqlite3.Connection,
) -> None:
    found = _by_tree(
        h for h in impact.of_delete(built, "prompts", "mine") if h.tree != "*"
    )

    assert set(found) == {"alpha"}  # beta's brief carries another template
    assert found["alpha"].stale.nodes == 2  # type: ignore[attr-defined]


def test_deleting_a_source_strands_its_sections_and_says_so(
    built: sqlite3.Connection,
) -> None:
    found = _by_tree(impact.of_delete(built, "sources", "a"))

    assert set(found) == {"alpha"}
    alpha = found["alpha"]
    assert alpha.stale.sections == 2 and alpha.stale.nodes == 2  # type: ignore[attr-defined]
    assert "stay in the tree" in alpha.reason  # type: ignore[attr-defined]
    assert "still names it" in alpha.reason  # type: ignore[attr-defined]


def test_an_unscoped_tree_holding_the_source_is_not_told_it_names_it(
    built: sqlite3.Connection,
) -> None:
    """A tree with no config maps every source, so nothing names this one and
    no later save of that tree is refused over it."""
    with built:
        _topic(built, "gamma", "a", "four.md")

    found = _by_tree(impact.of_delete(built, "sources", "a"))

    assert set(found) == {"alpha", "gamma"}
    assert "still names it" not in found["gamma"].reason  # type: ignore[attr-defined]


def test_deleting_a_connection_names_the_models_that_stop_working(
    built: sqlite3.Connection,
) -> None:
    found = impact.of_delete(built, "connections", "cc")

    (hit,) = [h for h in found if "nothing goes stale" in h.reason]
    assert hit.stale.nodes == 0
    assert hit.reason.endswith("haiku, sonnet")
    # and the registry's own verdict: both models now call through nothing
    assert any("which is not registered" in h.reason for h in found)


def test_deleting_something_nothing_uses_strands_nothing(
    built: sqlite3.Connection,
) -> None:
    _register(built, "connections", name="spare", provider="claude-code")

    assert impact.of_delete(built, "connections", "spare") == ()
    assert impact.of_delete(built, "trees", "alpha") == ()


def test_deleting_the_only_model_of_a_role_says_the_build_is_refused(
    conn: sqlite3.Connection,
) -> None:
    """One model with no role serves every writing role; take it away and the
    next build is refused, which is the resolvers' own answer."""
    _register(conn, "models", name="only", kind="text", model="m")

    (hit,) = [
        h
        for h in impact.of_delete(conn, "models", "only")
        if "role brief:" in h.reason
    ]

    assert hit.tree == "*" and "a build or sync is refused" in hit.reason
    assert registry_store.get(conn, "models", "only") is not None


def test_deleting_the_only_prompt_of_a_role_says_the_role_is_refused(
    conn: sqlite3.Connection,
) -> None:
    _register(conn, "prompts", name="mine", role="judge", template=TEMPLATE)

    found = impact.of_delete(conn, "prompts", "mine")

    (hit,) = [h for h in found if h.tree == "*" and "role judge" in h.reason]
    assert "a build or sync is refused" in hit.reason


def test_deleting_the_only_source_says_the_build_is_refused(
    conn: sqlite3.Connection,
) -> None:
    _register(conn, "sources", name="s1", type="git", url="x", auth={})

    found = impact.of_delete(conn, "sources", "s1")

    assert [h.reason for h in found] == [
        "after this, a build or sync is refused: no source is registered "
        "to read"
    ]


def test_the_delete_question_never_writes_to_the_database(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    """A read page: another connection holding the write lock must not make
    it wait or fail."""
    _register(conn, "sources", name="s1", type="git", url="x", auth={})
    other = sqlite3.connect(tmp_path / "hrono.db", isolation_level=None)
    other.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("PRAGMA busy_timeout = 0")
        found = impact.of_delete(conn, "sources", "s1")
    finally:
        other.execute("ROLLBACK")
        other.close()

    assert found
