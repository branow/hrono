"""Home and Health say what the next sync rewrites, before it runs.

A tree whose briefs were written by an older prompt is "up to date" by every
other measure; the sync that follows rewrites them at the admin's cost. The
page says so, with the count of model calls, and stops saying so once the
briefs are current.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.health import upgrade
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.registry import store as registry_store
from hrono.server.app import create_app
from hrono.summarize import briefs
from hrono.summarize.resolve import resolve_prompt, template_hash

KEY = Fernet.generate_key()
TREE = "default"


def _section(conn: object, path: str) -> int:
    body = f"{path} body\n".encode()
    digest = content_hash(body)
    istore.upsert_content(conn, digest, body)  # type: ignore[arg-type]
    return istore.insert_section(
        conn,  # type: ignore[arg-type]
        source="docs",
        address=Address("git", "ex/docs", path, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )


class Tree:
    def __init__(self, client: TestClient, conn: object, nodes: list[int]):
        self.client = client
        self.conn = conn
        self.nodes = nodes

    def write_briefs(self, hash_: str) -> None:
        with self.conn:  # type: ignore[attr-defined]
            for node in self.nodes:
                briefs.upsert(
                    self.conn,  # type: ignore[arg-type]
                    node,
                    f"A summary of node {node}: what its members hold.",
                    model_name="brief",
                    prompt_name="brief",
                    prompt_hash=hash_,
                    member_signature="sig",
                    input_tokens=1,
                    output_tokens=1,
                )

    def home(self, lang: str = "") -> str:
        if lang:
            self.client.cookies.set("hrono_lang", lang)
        return self.client.get(f"/ui?tree={TREE}").text

    def health(self) -> str:
        return self.client.get(f"/ui/trees/{TREE}/triage").text


@pytest.fixture
def tree(tmp_path: Path) -> Iterator[Tree]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    registry_store.insert(
        conn,
        "connections",
        "local",
        json.dumps(
            {
                "name": "local",
                "provider": "openai-compatible",
                "endpoint": "http://127.0.0.1:1/v1",
                "auth": {"method": "none"},
            }
        ),
        None,
        "t",
    )
    for role in ("brief", "brief-upper"):
        registry_store.insert(
            conn,
            "prompts",
            role,
            json.dumps(
                {"name": role, "role": role, "template": f"Write the {role}."}
            ),
            None,
            "t",
        )
        registry_store.insert(
            conn,
            "models",
            role,
            json.dumps(
                {
                    "name": role,
                    "kind": "text",
                    "connection": "local",
                    "model": "m",
                    "role": role,
                    "params": {},
                    "price": None,
                }
            ),
            None,
            "t",
        )
    with conn:
        nodes = [
            cluster_store.add_leaf_node(
                conn, TREE, [(_section(conn, f"{i}.md"), False, None)]
            )
            for i in range(3)
        ]
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        client.post("/ui/login", data={"token": token})
        yield Tree(client, conn, nodes)
    conn.close()


def test_briefs_from_an_older_prompt_are_announced_with_their_cost(
    tree: Tree,
) -> None:
    tree.write_briefs("an-older-prompt")

    home = tree.home()
    health = tree.health()

    assert 'id="rewrite"' in home
    assert "3 briefs were written by an older prompt" in home
    assert "about 3 model calls" in home
    assert "A second sync with nothing changed costs nothing." in home
    assert "/triage?tree=default#rewrite" in home
    assert 'id="rewrite"' in health
    assert health.count("written by an older prompt</td>") == 3


def test_current_briefs_say_nothing(tree: Tree) -> None:
    _, template = resolve_prompt(tree.conn, "brief")  # type: ignore[arg-type]
    tree.write_briefs(template_hash(template))

    assert 'id="rewrite"' not in tree.home()
    assert 'id="rewrite"' not in tree.health()


def test_the_announcement_reads_in_ukrainian(tree: Tree) -> None:
    tree.write_briefs("an-older-prompt")

    home = tree.home("uk")

    assert "Наступне оновлення перепише частину цього дерева" in home
    # the second sync is free, not the next one, which this line prices
    assert "Друге оновлення без змін нічого не коштує." in home


def test_sections_moving_to_their_condensations_are_announced(
    tree: Tree, monkeypatch: pytest.MonkeyPatch
) -> None:
    # briefs are current; what is left is placement: every member has a
    # condensation the tree never embedded, and each topic is over the cap,
    # so the sync splits each one in two and briefs both halves
    _, template = resolve_prompt(tree.conn, "brief")  # type: ignore[arg-type]
    tree.write_briefs(template_hash(template))
    monkeypatch.setattr(upgrade, "MAX_CAP", 0)
    with tree.conn:  # type: ignore[attr-defined]
        for name, kind, role in (
            ("emb", "embedding", None),
            ("cd", "text", "condense"),
        ):
            registry_store.insert(
                tree.conn,  # type: ignore[arg-type]
                "models",
                name,
                json.dumps(
                    {
                        "name": name,
                        "kind": kind,
                        "connection": None if role is None else "local",
                        "model": "m",
                        "role": role,
                        "params": {},
                        "price": None,
                    }
                ),
                None,
                "t",
            )
        for row in tree.conn.execute(
            "SELECT content_hash FROM sections"
        ).fetchall():  # type: ignore[attr-defined]
            tree.conn.execute(  # type: ignore[attr-defined]
                "INSERT INTO condensations VALUES (?, 'cd', ?, 1, 1, 't')",
                (row["content_hash"], f"condensed {row['content_hash']}"),
            )

    home = tree.home()

    assert "3 sections will be placed by their condensations" in home
    assert "about 6 model calls" in home
