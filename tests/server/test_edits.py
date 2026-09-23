"""#156: rename a topic, write its brief by hand, hand it back.

The three edits that make pins visible. What each test checks is not that the
endpoint answered 200 — it is that the PIPELINE then behaves differently,
because an edit the next run reverts is worse than no edit at all.
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
from hrono.export.render import _heading
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.server.app import create_app
from hrono.summarize import briefs

KEY = Fernet.generate_key()
TREE = "default"
BRIEF = "The deploy pipeline, as the model understood it."
HAND = "The deploy pipeline. Owned by platform; ask before changing it."


class Harness:
    def __init__(self, client: TestClient, conn: object, tokens: dict) -> None:
        self.client = client
        self.conn = conn
        self.tokens = tokens

    def auth(self, role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[role]}"}


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[tuple[Harness, int]]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
    }
    body = b"deploy steps\n"
    istore.upsert_content(conn, content_hash(body), body)
    section = istore.insert_section(
        conn,
        source="repo",
        address=Address("git", "ex/repo", "deploy.md", "v1"),
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=0,
    )
    with conn:
        node = cluster_store.add_leaf_node(conn, TREE, [(section, False, None)])
        briefs.upsert(
            conn,
            node,
            BRIEF,
            model_name="m",
            prompt_name="brief",
            prompt_hash="h",
            member_signature=briefs.member_signature(conn, node),
            input_tokens=1,
            output_tokens=1,
        )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        yield Harness(client, conn, tokens), node
    conn.close()


def test_a_rename_is_what_the_export_shows(
    harness: tuple[Harness, int],
) -> None:
    h, node = harness
    assert _heading(h.conn, node).startswith("The deploy pipeline")

    response = h.client.patch(
        f"/trees/{TREE}/nodes/{node}",
        json={"title": "Deploys (platform-owned)"},
        headers=h.auth("admin"),
    )

    assert response.status_code == 200
    assert _heading(h.conn, node) == "Deploys (platform-owned)"


def test_a_rename_pins_the_brief_it_was_derived_from(
    harness: tuple[Harness, int],
) -> None:
    # without this the next regeneration rewrites the line the title came
    # from, and the operator's name is quietly back in the model's hands.
    h, node = harness

    h.client.patch(
        f"/trees/{TREE}/nodes/{node}",
        json={"title": "Deploys"},
        headers=h.auth("admin"),
    )

    assert pins.is_pinned(h.conn, pins.BRIEF, node) is True


def test_an_overridden_brief_is_stored_indexed_and_pinned(
    harness: tuple[Harness, int],
) -> None:
    h, node = harness

    response = h.client.put(
        f"/trees/{TREE}/nodes/{node}/brief",
        json={"text": HAND},
        headers=h.auth("admin"),
    )

    assert response.status_code == 200
    assert str(briefs.get(h.conn, node)["text"]) == HAND
    assert pins.is_pinned(h.conn, pins.BRIEF, node) is True
    # recall must answer from the operator's words, so the node:// passages
    # are rebuilt too (#071) — not only the stored row.
    indexed = h.conn.execute(
        "SELECT COUNT(*) FROM passages_fts WHERE source = ?",
        (f"node-{node}",),
    ).fetchone()[0]
    assert int(indexed) > 0


def test_unpin_hands_the_node_back(harness: tuple[Harness, int]) -> None:
    h, node = harness
    h.client.put(
        f"/trees/{TREE}/nodes/{node}/brief",
        json={"text": HAND},
        headers=h.auth("admin"),
    )

    response = h.client.post(
        f"/trees/{TREE}/nodes/{node}/unpin", headers=h.auth("admin")
    )

    assert response.status_code == 200
    assert response.json()["released"] == 1
    assert pins.is_pinned(h.conn, pins.BRIEF, node) is False


def test_every_edit_is_admin_only(harness: tuple[Harness, int]) -> None:
    h, node = harness
    for role in ("reader", "writer"):
        assert (
            h.client.patch(
                f"/trees/{TREE}/nodes/{node}",
                json={"title": "x"},
                headers=h.auth(role),
            ).status_code
            == 403
        )
        assert (
            h.client.put(
                f"/trees/{TREE}/nodes/{node}/brief",
                json={"text": "x"},
                headers=h.auth(role),
            ).status_code
            == 403
        )
        assert (
            h.client.post(
                f"/trees/{TREE}/nodes/{node}/unpin", headers=h.auth(role)
            ).status_code
            == 403
        )
    assert h.client.patch(f"/trees/{TREE}/nodes/{node}").status_code == 401


def test_a_node_of_another_tree_is_not_found_here(
    harness: tuple[Harness, int],
) -> None:
    # the tree in the path is part of the address, not decoration: renaming
    # "node 4" while looking at the wrong tree must fail, not rename node 4.
    h, node = harness

    response = h.client.patch(
        f"/trees/other/nodes/{node}",
        json={"title": "x"},
        headers=h.auth("admin"),
    )

    assert response.status_code == 404
    assert (
        h.conn.execute(
            "SELECT title FROM nodes WHERE id = ?", (node,)
        ).fetchone()["title"]
        is None
    )


def test_an_empty_title_or_brief_is_refused(
    harness: tuple[Harness, int],
) -> None:
    h, node = harness
    assert (
        h.client.patch(
            f"/trees/{TREE}/nodes/{node}",
            json={"title": ""},
            headers=h.auth("admin"),
        ).status_code
        == 422
    )
    assert (
        h.client.put(
            f"/trees/{TREE}/nodes/{node}/brief",
            json={"text": ""},
            headers=h.auth("admin"),
        ).status_code
        == 422
    )


def test_an_unknown_node_is_404(harness: tuple[Harness, int]) -> None:
    h, _node = harness
    assert (
        h.client.post(
            f"/trees/{TREE}/nodes/99999/unpin", headers=h.auth("admin")
        ).status_code
        == 404
    )
