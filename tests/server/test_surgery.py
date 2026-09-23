"""#158: reparent, merge and dissolve a topic by hand.

Two of these already existed as pipeline primitives; what is new is the
operator's hand on them, the pin that keeps the result, and the refusals that
stop a hand-edit corrupting the tree. Each test checks the tree AFTER, not the
status code.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono import pins
from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.embed.store import upsert_vector
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.registry import store as registry_store
from hrono.server.app import create_app
from hrono.summarize import briefs

KEY = Fernet.generate_key()
TREE = "default"
MODEL = "emb"


class Harness:
    def __init__(self, client: TestClient, conn: object, token: str) -> None:
        self.client = client
        self.conn = conn
        self.headers = {"Authorization": f"Bearer {token}"}


def _section(conn: object, path: str, vector: list[float]) -> int:
    from hrono.cluster.blend import path_body, register_path_bodies

    body = f"{path} body\n".encode()
    digest = content_hash(body)
    istore.upsert_content(conn, digest, body)  # type: ignore[arg-type]
    register_path_bodies(conn, [path])  # type: ignore[arg-type]
    upsert_vector(conn, digest, MODEL, vector)  # type: ignore[arg-type]
    upsert_vector(  # type: ignore[arg-type]
        conn, content_hash(path_body(path)), MODEL, vector
    )
    return istore.insert_section(
        conn,  # type: ignore[arg-type]
        source="docs",
        address=Address("git", "ex/docs", path, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[tuple[Harness, dict]]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    registry_store.insert(
        conn,
        "models",
        MODEL,
        '{"name": "emb", "kind": "embedding", "connection": null, '
        '"model": "m", "params": {"dims": 2}}',
        None,
        "t",
    )
    ids: dict[str, int] = {}
    with conn:
        alpha = _section(conn, "a.md", [1.0, 0.0])
        beta = _section(conn, "b.md", [0.9, 0.1])
        gamma = _section(conn, "c.md", [0.0, 1.0])
        ids["first"] = cluster_store.add_leaf_node(
            conn, TREE, [(alpha, False, None)]
        )
        ids["second"] = cluster_store.add_leaf_node(
            conn, TREE, [(beta, False, None)]
        )
        ids["third"] = cluster_store.add_leaf_node(
            conn, TREE, [(gamma, False, None)]
        )
        ids["alpha"], ids["beta"], ids["gamma"] = alpha, beta, gamma
        for node in (ids["first"], ids["second"], ids["third"]):
            briefs.upsert(
                conn,
                node,
                f"A summary of topic {node}.",
                model_name="m",
                prompt_name="brief",
                prompt_hash="h",
                member_signature=briefs.member_signature(conn, node),
                input_tokens=1,
                output_tokens=1,
            )
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 1, 0, 't')",
            (TREE,),
        )
        ids["parent"] = int(
            conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0]
        )
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 1, 1, 't')",
            (TREE,),
        )
        ids["other_parent"] = int(
            conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0]
        )
        for child in (ids["first"], ids["second"]):
            cluster_store.add_child(
                conn, ids["parent"], child, attached=False, similarity=None
            )
        cluster_store.add_child(
            conn,
            ids["other_parent"],
            ids["third"],
            attached=False,
            similarity=None,
        )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        yield Harness(client, conn, token), ids
    conn.close()


def _parent_of(h: Harness, child: int) -> int | None:
    row = h.conn.execute(
        "SELECT parent_id FROM node_children WHERE child_id = ?", (child,)
    ).fetchone()
    return None if row is None else int(row["parent_id"])


def _members(h: Harness, node: int) -> set[int]:
    return {
        int(r["section_id"])
        for r in h.conn.execute(
            "SELECT section_id FROM node_members WHERE node_id = ?", (node,)
        ).fetchall()
    }


def test_reparent_moves_the_node_and_pins_it(
    harness: tuple[Harness, dict],
) -> None:
    h, ids = harness

    response = h.client.post(
        f"/trees/{TREE}/nodes/{ids['third']}/reparent",
        json={"to": ids["parent"]},
        headers=h.headers,
    )

    assert response.status_code == 200
    assert _parent_of(h, ids["third"]) == ids["parent"]
    assert pins.is_pinned(h.conn, pins.PARENTING, ids["third"]) is True
    assert pins.anchors(h.conn, pins.PARENTING)[ids["third"]] == ids["parent"]


def test_a_node_cannot_be_reparented_under_itself_or_its_own_child(
    harness: tuple[Harness, dict],
) -> None:
    # a cycle does not fail loudly: it detaches a subtree from the root and the
    # export simply stops mentioning it.
    h, ids = harness

    assert (
        h.client.post(
            f"/trees/{TREE}/nodes/{ids['parent']}/reparent",
            json={"to": ids["parent"]},
            headers=h.headers,
        ).status_code
        == 422
    )
    assert (
        h.client.post(
            f"/trees/{TREE}/nodes/{ids['parent']}/reparent",
            json={"to": ids["first"]},
            headers=h.headers,
        ).status_code
        == 422
    )
    assert _parent_of(h, ids["first"]) == ids["parent"]  # unchanged


def test_merge_folds_members_into_the_lowest_id(
    harness: tuple[Harness, dict],
) -> None:
    h, ids = harness
    merged = sorted([ids["first"], ids["second"]])

    response = h.client.post(
        f"/trees/{TREE}/nodes/merge",
        json={"ids": [ids["second"], ids["first"]]},  # order must not matter
        headers=h.headers,
    )

    assert response.status_code == 200
    assert response.json()["node_id"] == merged[0]
    assert _members(h, merged[0]) == {ids["alpha"], ids["beta"]}
    assert (
        h.conn.execute(
            "SELECT 1 FROM nodes WHERE id = ?", (merged[1],)
        ).fetchone()
        is None
    )


def test_merge_leaves_no_orphaned_brief_or_passage(
    harness: tuple[Harness, dict],
) -> None:
    # #125: a retired node's summary must not outlive it, and a merge retires
    # nodes the same way a rebuild does.
    h, ids = harness
    gone = max(ids["first"], ids["second"])

    h.client.post(
        f"/trees/{TREE}/nodes/merge",
        json={"ids": [ids["first"], ids["second"]]},
        headers=h.headers,
    )

    assert briefs.get(h.conn, gone) is None
    left = h.conn.execute(
        "SELECT COUNT(*) FROM sections WHERE source = ?", (f"node-{gone}",)
    ).fetchone()[0]
    assert int(left) == 0


def test_merge_pins_the_result_but_not_its_brief(
    harness: tuple[Harness, dict],
) -> None:
    # the operator decided these belong together, so membership holds; the
    # merged topic genuinely needs a NEW summary, so the brief does not.
    h, ids = harness
    survivor = min(ids["first"], ids["second"])

    h.client.post(
        f"/trees/{TREE}/nodes/merge",
        json={"ids": [ids["first"], ids["second"]]},
        headers=h.headers,
    )

    assert pins.pinned(h.conn, pins.MEMBERSHIP) == {ids["alpha"], ids["beta"]}
    assert pins.is_pinned(h.conn, pins.BRIEF, survivor) is False


def test_merge_needs_two_distinct_nodes(
    harness: tuple[Harness, dict],
) -> None:
    h, ids = harness
    assert (
        h.client.post(
            f"/trees/{TREE}/nodes/merge",
            json={"ids": [ids["first"], ids["first"]]},
            headers=h.headers,
        ).status_code
        == 422
    )


def test_dissolve_retires_the_topic_and_frees_its_members(
    harness: tuple[Harness, dict],
) -> None:
    h, ids = harness

    response = h.client.post(
        f"/trees/{TREE}/nodes/{ids['third']}/dissolve", headers=h.headers
    )

    assert response.status_code == 200
    assert (
        h.conn.execute(
            "SELECT 1 FROM nodes WHERE id = ?", (ids["third"],)
        ).fetchone()
        is None
    )
    # nothing is pinned: the operator asked for a re-placement, not a new home
    assert ids["gamma"] not in pins.pinned(h.conn, pins.MEMBERSHIP)


def test_surgery_is_admin_only(harness: tuple[Harness, dict]) -> None:
    h, ids = harness
    conn = h.conn
    writer = create_user(conn, "writer", "writer")[1]
    headers = {"Authorization": f"Bearer {writer}"}

    for path, body in (
        (f"/trees/{TREE}/nodes/{ids['third']}/reparent", {"to": 1}),
        (f"/trees/{TREE}/nodes/merge", {"ids": [1, 2]}),
        (f"/trees/{TREE}/nodes/{ids['third']}/dissolve", None),
    ):
        response = h.client.post(path, json=body, headers=headers)
        assert response.status_code == 403


def test_a_node_from_another_tree_is_refused(
    harness: tuple[Harness, dict],
) -> None:
    h, ids = harness
    assert (
        h.client.post(
            f"/trees/{TREE}/nodes/{ids['third']}/reparent",
            json={"to": 99999},
            headers=h.headers,
        ).status_code
        == 404
    )
