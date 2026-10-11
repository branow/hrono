"""An operator divides a topic they can see is really two.

`repair.split` already IS the scoped mini-pipeline; what is new is that a human
can ask for it, and that the size rule which governs the automatic repair does
not govern them — a six-member topic is exactly the case they would ask about.
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
def harness(tmp_path: Path) -> Iterator[tuple[Harness, int, list[int]]]:
    """One node holding two separate groups, plus strays between them."""
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
    with conn:
        # the clustering ladder floors at 12 points and a manual
        # split runs that same real recipe, so a divisible topic has at
        # least that many members.
        left = [_section(conn, f"l{i}.md", [1.0, 0.01 * i]) for i in range(8)]
        right = [_section(conn, f"r{i}.md", [0.01 * i, 1.0]) for i in range(8)]
        # strays between the two groups: HDBSCAN calls them noise, and a
        # split that keeps only its density cores would silently lose them.
        stray = [
            _section(conn, f"s{i}.md", [0.7, 0.7 + 0.01 * i]) for i in (0, 1)
        ]
        members = left + right + stray
        node = cluster_store.add_leaf_node(
            conn, TREE, [(sid, False, None) for sid in members]
        )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        yield Harness(client, conn, token), node, members
    conn.close()


def _members_by_node(h: Harness) -> dict[int, set[int]]:
    out: dict[int, set[int]] = {}
    for row in h.conn.execute(
        "SELECT node_id, section_id FROM node_members"
    ).fetchall():
        out.setdefault(int(row["node_id"]), set()).add(int(row["section_id"]))
    return out


def test_a_split_divides_the_topic_and_keeps_every_member(
    harness: tuple[Harness, int, list[int]],
) -> None:
    # sixteen members is far below MAX_CAP (30), which is the summarization
    # budget the AUTOMATIC repair answers to. An operator is not asking about
    # a budget; they can see two topics.
    h, node, sections = harness

    response = h.client.post(
        f"/trees/{TREE}/nodes/{node}/split", headers=h.headers
    )

    assert response.status_code == 200, response.json()
    children = response.json()["children"]
    assert len(children) >= 2
    placed = _members_by_node(h)
    assert node not in placed  # the divided node retired
    assert set().union(*(placed[c] for c in children)) == set(sections)


def test_a_topic_that_does_not_divide_is_refused_and_left_intact(
    harness: tuple[Harness, int, list[int]],
) -> None:
    # one dense group is not two topics, and saying so is better than silently
    # doing nothing or inventing a division.
    h, _node, _sections = harness
    with h.conn:
        # identical vectors: HDBSCAN finds no density core at all, which is
        # what "one topic, not two" looks like to the recipe. A merely TIGHT
        # group still splits — the recipe is better at finding structure than
        # a hand-written fixture is at hiding it.
        dense = [_section(h.conn, f"d{i}.md", [1.0, 0.0]) for i in range(14)]
        node = cluster_store.add_leaf_node(
            h.conn, TREE, [(sid, False, None) for sid in dense]
        )

    response = h.client.post(
        f"/trees/{TREE}/nodes/{node}/split", headers=h.headers
    )

    assert response.status_code == 422
    assert "divide" in response.json()["error"]["message"]
    assert _members_by_node(h)[node] == set(dense)


@pytest.mark.parametrize("held", [1, 4])
def test_a_topic_below_the_ladders_floor_says_so(
    harness: tuple[Harness, int, list[int]], held: int
) -> None:
    # below the recipe's floor there is no honest reduction to run, so there
    # is nothing to divide BY. The message has to say that rather than
    # "does not divide", which would send an operator looking for a boundary
    # -- and a topic of ONE says it just as much as a topic of four.
    h, _node, _sections = harness
    with h.conn:
        few = [
            _section(h.conn, f"f{held}_{i}.md", [1.0, float(i)])
            for i in range(held)
        ]
        small = cluster_store.add_leaf_node(
            h.conn, TREE, [(sid, False, None) for sid in few]
        )

    response = h.client.post(
        f"/trees/{TREE}/nodes/{small}/split", headers=h.headers
    )

    assert response.status_code == 422
    assert "too few members" in response.json()["error"]["message"]
    assert _members_by_node(h)[small] == set(few)


def test_an_unknown_topic_is_not_found(
    harness: tuple[Harness, int, list[int]],
) -> None:
    h, _node, _sections = harness

    response = h.client.post(
        f"/trees/{TREE}/nodes/99999/split", headers=h.headers
    )

    assert response.status_code == 404


def test_a_split_pins_nothing(
    harness: tuple[Harness, int, list[int]],
) -> None:
    # the operator asked for a division; where each member lands inside it is
    # still the pipeline's judgement, which is what they asked it to redo.
    h, node, _sections = harness

    h.client.post(f"/trees/{TREE}/nodes/{node}/split", headers=h.headers)

    assert pins.pinned(h.conn, pins.MEMBERSHIP) == frozenset()


def test_an_unknown_topic_is_not_found_without_an_embedding_model(
    tmp_path: Path,
) -> None:
    # driving a real server found this: the endpoint resolved the embedding
    # model before it confirmed the node, so a server with no model answered
    # an unknown id with a 500 instead of a 404.
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    app = create_app(connection=conn, master_key=KEY, key_id=1)

    with TestClient(app) as client:
        response = client.post(
            f"/trees/{TREE}/nodes/99999/split",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    conn.close()


def test_split_is_admin_only(
    harness: tuple[Harness, int, list[int]],
) -> None:
    h, node, _sections = harness
    writer = create_user(h.conn, "writer", "writer")[1]

    response = h.client.post(
        f"/trees/{TREE}/nodes/{node}/split",
        headers={"Authorization": f"Bearer {writer}"},
    )

    assert response.status_code == 403


def test_a_pin_follows_the_chunk_into_the_child_it_lands_in(
    harness: tuple[Harness, int, list[int]],
) -> None:
    # the operator's whole story: file a chunk under this topic, then divide
    # the topic. Their first decision is about the chunk's company, and the
    # division does not change that company -- it narrows it.
    h, node, _sections = harness
    with h.conn:
        stray = _section(h.conn, "stray.md", [1.0, 0.02])
        origin = cluster_store.add_leaf_node(
            h.conn, TREE, [(stray, False, None)]
        )
    assert origin is not None

    moved = h.client.post(
        f"/trees/{TREE}/sections/{stray}/move",
        json={"to_node": node},
        headers=h.headers,
    )
    assert moved.status_code == 200

    response = h.client.post(
        f"/trees/{TREE}/nodes/{node}/split", headers=h.headers
    )

    assert response.status_code == 200, response.json()
    anchor = pins.anchors(h.conn, pins.MEMBERSHIP)[stray]
    assert anchor in response.json()["children"]
    members = {
        int(r["section_id"])
        for r in h.conn.execute(
            "SELECT section_id FROM node_members WHERE node_id = ?", (anchor,)
        ).fetchall()
    }
    assert stray in members
