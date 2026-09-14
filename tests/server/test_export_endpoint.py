"""T31: the GET export endpoint over collapse (#078) + render (#079)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.server.app import create_app
from hrono.summarize import briefs

KEY = Fernet.generate_key()
TREE = "default"


def add_section(conn: object, path: str, body: bytes) -> int:
    istore.upsert_content(conn, content_hash(body), body)  # type: ignore[arg-type]
    sid = istore.insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "ex/repo", path, "v1"),
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=0,
    )
    istore.insert_passage(
        conn,  # type: ignore[arg-type]
        section_id=sid,
        source="repo",
        address=Address("git", "ex/repo", path, "v1"),
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        sp_paths=(),
        ordinal=0,
    )
    return sid


def brief(conn: object, node_id: int, text: str) -> None:
    briefs.upsert(
        conn,  # type: ignore[arg-type]
        node_id,
        text,
        model_name="m",
        prompt_name="brief",
        prompt_hash="h",
        member_signature="sig",
        input_tokens=1,
        output_tokens=1,
    )


class Harness:
    def __init__(self, client: TestClient, tokens: dict[str, str]) -> None:
        self.client = client
        self.tokens = tokens

    def auth(self, role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[role]}"}


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1] for role in ("reader", "writer")
    }
    s0 = add_section(conn, "a.py", b"alpha body\n")
    s1 = add_section(conn, "b.py", b"beta body\n")
    cluster_store.replace_tree(
        conn,
        TREE,
        0,
        [(0, s0, False, None), (1, s1, False, None)],
        [(s0, [0.1]), (s1, [0.2])],
    )
    level0 = [
        int(r["id"])
        for r in conn.execute(
            "SELECT id FROM nodes WHERE level = 0 ORDER BY id"
        ).fetchall()
    ]
    cluster_store.replace_level(
        conn,
        TREE,
        1,
        [(0, level0[0], False, None), (0, level0[1], False, None)],
    )
    root = int(
        conn.execute("SELECT id FROM nodes WHERE level = 1").fetchone()["id"]
    )
    brief(conn, level0[0], "# Alpha\n\nAlpha.")
    brief(conn, level0[1], "# Beta\n\nBeta.")
    brief(conn, root, "# Root\n\nOverview.")
    conn.commit()
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        yield Harness(client, tokens)
    conn.close()


def test_unauthenticated_is_rejected(harness: Harness) -> None:
    assert harness.client.get("/trees/default/export").status_code == 401


def test_reader_gets_the_rendered_manifest(harness: Harness) -> None:
    resp = harness.client.get(
        "/trees/default/export", headers=harness.auth("reader")
    )
    assert resp.status_code == 200
    files = {f["path"]: f["content"] for f in resp.json()["files"]}
    assert "root.md" in files
    assert "# Root" in files["root.md"]
    assert any(p.endswith("/brief.md") for p in files)  # child topics rendered


def test_unbuilt_tree_is_a_clean_404(harness: Harness) -> None:
    resp = harness.client.get(
        "/trees/ghost/export", headers=harness.auth("reader")
    )
    assert resp.status_code == 404


def test_levels_below_two_does_not_500(harness: Harness) -> None:
    resp = harness.client.get(
        "/trees/default/export?levels=1", headers=harness.auth("reader")
    )
    assert resp.status_code == 200  # floored to 2, not an error


def test_non_integer_levels_is_a_clean_422(harness: Harness) -> None:
    resp = harness.client.get(
        "/trees/default/export?levels=abc", headers=harness.auth("reader")
    )
    assert resp.status_code == 422


def test_every_manifest_path_is_relative(harness: Harness) -> None:
    resp = harness.client.get(
        "/trees/default/export", headers=harness.auth("reader")
    )
    paths = [f["path"] for f in resp.json()["files"]]
    assert paths
    assert not [p for p in paths if p.startswith("/")]
    assert len(paths) == len(set(paths))


def test_a_root_carrying_sections_serves_relative_paths(
    tmp_path: Path,
) -> None:
    # F19 end to end: the root's own sections were served as "/<name>.md", so
    # `hrono tree export` refused the first entry and wrote nothing at all.
    conn = open_database(tmp_path / "flat.db")
    reconcile(conn, KEY)
    token = create_user(conn, "reader", "reader")[1]
    s0 = add_section(conn, "a.py", b"alpha body\n")
    s1 = add_section(conn, "b.py", b"beta body\n")
    cluster_store.replace_tree(
        conn,
        TREE,
        0,
        [(0, s0, False, None), (0, s1, False, None)],
        [(s0, [0.1]), (s1, [0.2])],
    )
    root = int(conn.execute("SELECT id FROM nodes").fetchone()["id"])
    brief(conn, root, "# Only topic\n\nAll of it.")
    conn.commit()
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        resp = client.get(
            "/trees/default/export",
            headers={"Authorization": f"Bearer {token}"},
        )
    conn.close()
    assert resp.status_code == 200
    paths = sorted(f["path"] for f in resp.json()["files"])
    assert paths == [f"a-py-{s0}.md", f"b-py-{s1}.md", "root.md"]


def test_a_tree_that_is_not_built_to_one_root_fails_loudly(
    tmp_path: Path,
) -> None:
    # F20: seven parentless nodes rendered ONE /brief.md and silently dropped
    # six briefs. A forest is not a shape to render; it is a broken build.
    conn = open_database(tmp_path / "forest.db")
    reconcile(conn, KEY)
    token = create_user(conn, "reader", "reader")[1]
    s0 = add_section(conn, "a.py", b"alpha body\n")
    s1 = add_section(conn, "b.py", b"beta body\n")
    cluster_store.replace_tree(
        conn,
        TREE,
        0,
        [(0, s0, False, None), (1, s1, False, None)],
        [(s0, [0.1]), (s1, [0.2])],
    )
    for node in conn.execute("SELECT id FROM nodes WHERE level = 0").fetchall():
        brief(conn, int(node["id"]), "# Topic\n\nOne of several.")
    conn.commit()
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get(
            "/trees/default/export",
            headers={"Authorization": f"Bearer {token}"},
        )
    conn.close()
    assert resp.status_code == 500
    assert "single root" in resp.json()["error"]["message"]
