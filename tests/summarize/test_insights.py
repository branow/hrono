"""The count of unreviewed brief characters, derived from stored rows."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.db.database import Database
from hrono.registry import completeness, store
from hrono.summarize import insights
from hrono.summarize.resolve import resolve_text_model


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[object]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as c:
        yield c
    database.close()


def _node(conn, level: int, size: int, written: str = "2026-01-01") -> int:  # type: ignore[no-untyped-def]
    node = int(
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES ('t', ?, -1, 'x')",
            (level,),
        ).lastrowid
    )
    conn.execute(
        "INSERT INTO briefs(node_id, text, model_name, prompt_name, "
        "prompt_hash, member_signature, input_tokens, output_tokens, "
        "created_at) VALUES (?, ?, 'm', 'p', 'h', 's', 0, 0, ?)",
        (node, "x" * size, written),
    )
    return node


def _link(conn, parent: int, *children: int) -> None:  # type: ignore[no-untyped-def]
    for child in children:
        conn.execute(
            "INSERT INTO node_children(parent_id, child_id, attached, "
            "created_at) VALUES (?, ?, 0, 'x')",
            (parent, child),
        )


def _pass(conn, node: int, at: str) -> None:  # type: ignore[no-untyped-def]
    conn.execute(
        "INSERT INTO insights_passes(node_id, passed_at, model_name, version) "
        "VALUES (?, ?, 'opus', 's')",
        (node, at),
    )


def _shape(conn):  # type: ignore[no-untyped-def]
    """root <- mid <- (a, b); root <- c."""
    a, b, c = (_node(conn, 0, size) for size in (100, 200, 400))
    mid = _node(conn, 1, 30)
    root = _node(conn, 2, 20)
    _link(conn, mid, a, b)
    _link(conn, root, mid, c)
    return a, b, c, mid, root


def test_a_parent_counts_the_briefs_below_it_and_a_leaf_none(conn) -> None:  # type: ignore[no-untyped-def]
    a, b, c, mid, root = _shape(conn)

    counted = insights.unreviewed(conn, "t")

    assert counted[mid] == 300  # a and b, not its own brief
    assert counted[root] == 30 + 100 + 200 + 400  # every brief below it
    assert counted[a] == 0


def test_a_pass_takes_its_subtree_out_of_the_count_above(conn) -> None:  # type: ignore[no-untyped-def]
    a, b, c, mid, root = _shape(conn)
    _pass(conn, mid, "2026-02-01")

    counted = insights.unreviewed(conn, "t")

    assert counted[mid] == 0  # a, b and the extended brief are covered
    assert counted[root] == 400  # only c is left unreviewed


def test_a_brief_rewritten_after_the_pass_counts_again(conn) -> None:  # type: ignore[no-untyped-def]
    a, b, c, mid, root = _shape(conn)
    _pass(conn, mid, "2026-02-01")
    conn.execute(
        "UPDATE briefs SET created_at = '2026-03-01' WHERE node_id = ?", (b,)
    )

    counted = insights.unreviewed(conn, "t")

    assert counted[mid] == 200
    assert counted[root] == 600


def test_passes_climb_like_a_build_and_the_root_is_always_one(conn) -> None:  # type: ignore[no-untyped-def]
    a, b, c, mid, root = _shape(conn)

    low = insights.passes_for(conn, "t", 250)
    high = insights.passes_for(conn, "t", 10_000)

    assert [p.node for p in low] == [mid, root]
    assert low[1].characters == 400  # what mid's pass left under the root
    assert [p.node for p in high] == [root]
    assert high[0].characters == 730


def test_insights_never_stands_in_for_a_build_role(conn) -> None:  # type: ignore[no-untyped-def]
    for name, role in (("sonnet", None), ("opus", "insights")):
        body = {"name": name, "kind": "text", "connection": "c", "model": name}
        if role:
            body["role"] = role
        store.insert(conn, "models", name, json.dumps(body), None, "t")

    # one build model plus the reviewer is still a one-model install
    assert resolve_text_model(conn, {}, "brief")["name"] == "sonnet"
    assert resolve_text_model(conn, {}, "insights")["name"] == "opus"
    assert not [
        g for g in completeness.gaps(conn) if "multiple text models" in g.says
    ]


@pytest.mark.parametrize(
    ("provider", "estimate"), [("claude-code", True), ("anthropic", False)]
)
def test_a_subscription_reviewer_marks_the_cost_an_estimate(
    conn, provider: str, estimate: bool
) -> None:  # type: ignore[no-untyped-def]
    _shape(conn)
    store.insert(
        conn,
        "connections",
        "c",
        json.dumps({"name": "c", "provider": provider}),
        None,
        "t",
    )
    store.insert(
        conn,
        "models",
        "opus",
        json.dumps(
            {
                "name": "opus",
                "kind": "text",
                "connection": "c",
                "role": "insights",
            }
        ),
        None,
        "t",
    )

    plan = insights.plan_for(conn, "t", True, 10_000)

    assert plan.usd == 2.82 and plan.note is None
    assert (
        "an estimate of what the API would charge" in plan.basis
    ) is estimate
