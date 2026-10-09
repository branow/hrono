"""A human note, and the agent reading the tree sees it.

The spec's reason for this feature is the export, not the dashboard: "a human
'deprecated, use X' annotation flows into the rendered tree so the traversing
agent sees it." So the test that matters renders the tree and looks for the
words, under a heading that tells an agent a person wrote them.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono import notes, pins
from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.export.collapse import ExportNode, ExportTree
from hrono.export.render import render
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.server.app import create_app
from hrono.summarize import briefs

KEY = Fernet.generate_key()
TREE = "default"
DEPRECATED = "Deprecated. Use the platform pipeline instead."
LATER = "Actually retired entirely in September."


class Harness:
    def __init__(self, client: TestClient, conn: object, tokens: dict) -> None:
        self.client = client
        self.conn = conn
        self.tokens = tokens

    def auth(self, role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[role]}"}


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[tuple[Harness, int, int]]:
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
            "The deploy pipeline, as the model understood it.",
            model_name="m",
            prompt_name="brief",
            prompt_hash="h",
            member_signature=briefs.member_signature(conn, node),
            input_tokens=1,
            output_tokens=1,
        )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        yield Harness(client, conn, tokens), node, section
    conn.close()


def _rendered(h: Harness, node: int) -> str:
    tree = ExportTree(
        root=node,
        levels=1,
        nodes={
            node: ExportNode(node_id=node, level=0, children=(), sections=())
        },
    )
    files = render(h.conn, tree, notes=notes.rendered(h.conn, notes.NODE))
    return files["root.md"]


def test_a_note_reaches_the_rendered_tree(
    harness: tuple[Harness, int, int],
) -> None:
    h, node, _section = harness
    assert DEPRECATED not in _rendered(h, node)

    response = h.client.post(
        f"/trees/{TREE}/nodes/{node}/notes",
        json={"text": DEPRECATED},
        headers=h.auth("admin"),
    )

    assert response.status_code == 200
    page = _rendered(h, node)
    assert DEPRECATED in page
    # under its own heading: an agent must be able to tell a person's words
    # from a model's summary, which is the whole value.
    assert "## Notes" in page


def test_the_export_ENDPOINT_carries_the_note(
    harness: tuple[Harness, int, int],
) -> None:
    # the render helper above proves the renderer; this proves the SURFACE an
    # agent actually reads. Removing the notes argument from the endpoint left
    # every other test in this file green.
    h, node, _section = harness
    h.client.post(
        f"/trees/{TREE}/nodes/{node}/notes",
        json={"text": DEPRECATED},
        headers=h.auth("admin"),
    )

    response = h.client.get(f"/trees/{TREE}/export", headers=h.auth("reader"))

    assert response.status_code == 200
    pages = "\n".join(f["content"] for f in response.json()["files"])
    assert DEPRECATED in pages
    assert "## Notes" in pages


def test_a_second_note_does_not_replace_the_first(
    harness: tuple[Harness, int, int],
) -> None:
    h, node, _section = harness
    for text in (DEPRECATED, LATER):
        h.client.post(
            f"/trees/{TREE}/nodes/{node}/notes",
            json={"text": text},
            headers=h.auth("admin"),
        )

    page = _rendered(h, node)
    assert DEPRECATED in page
    assert LATER in page
    assert page.index(LATER) < page.index(DEPRECATED)  # newest first

    listed = h.client.get(
        f"/trees/{TREE}/nodes/{node}/notes", headers=h.auth("reader")
    ).json()["notes"]
    assert [n["text"] for n in listed] == [LATER, DEPRECATED]


def test_a_section_can_be_annotated_too(
    harness: tuple[Harness, int, int],
) -> None:
    h, _node, section = harness

    response = h.client.post(
        f"/trees/{TREE}/sections/{section}/notes",
        json={"text": "This file is generated; edit the template."},
        headers=h.auth("admin"),
    )

    assert response.status_code == 200
    listed = h.client.get(
        f"/trees/{TREE}/sections/{section}/notes", headers=h.auth("reader")
    ).json()["notes"]
    assert len(listed) == 1


def test_a_note_does_not_pin(harness: tuple[Harness, int, int]) -> None:
    # annotating a topic is not correcting the map: a comment that froze the
    # tree against every later update would be a trap for whoever left it.
    h, node, _section = harness

    h.client.post(
        f"/trees/{TREE}/nodes/{node}/notes",
        json={"text": DEPRECATED},
        headers=h.auth("admin"),
    )

    assert pins.is_pinned(h.conn, pins.BRIEF, node) is False


def test_writing_a_note_is_admin_only(
    harness: tuple[Harness, int, int],
) -> None:
    h, node, _section = harness
    for role in ("reader", "writer"):
        assert (
            h.client.post(
                f"/trees/{TREE}/nodes/{node}/notes",
                json={"text": "x"},
                headers=h.auth(role),
            ).status_code
            == 403
        )
    # reading is not: an agent's operator should see what a colleague wrote
    assert (
        h.client.get(
            f"/trees/{TREE}/nodes/{node}/notes", headers=h.auth("reader")
        ).status_code
        == 200
    )


def test_a_retired_node_takes_its_notes_with_it(
    harness: tuple[Harness, int, int],
) -> None:
    h, node, _section = harness
    h.client.post(
        f"/trees/{TREE}/nodes/{node}/notes",
        json={"text": DEPRECATED},
        headers=h.auth("admin"),
    )

    with h.conn:
        cluster_store.delete_node(h.conn, node)

    assert notes.get(h.conn, notes.NODE, node) == ()


def test_an_unknown_target_is_404(
    harness: tuple[Harness, int, int],
) -> None:
    h, _node, _section = harness
    assert (
        h.client.post(
            f"/trees/{TREE}/nodes/99999/notes",
            json={"text": "x"},
            headers=h.auth("admin"),
        ).status_code
        == 404
    )
    assert (
        h.client.post(
            f"/trees/{TREE}/sections/99999/notes",
            json={"text": "x"},
            headers=h.auth("admin"),
        ).status_code
        == 404
    )
