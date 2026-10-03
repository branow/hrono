"""#205: the Export page — the shape, the pages, the archive, for any role."""

import io
import re
import zipfile
from collections.abc import Iterator
from html import unescape
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.server.app import create_app
from hrono.summarize import briefs
from hrono.tree.commands import _materialize
from tests.server.test_export_endpoint import add_section

KEY = Fernet.generate_key()
TREE = "default"


class Panel:
    def __init__(self, client: TestClient, tokens: dict[str, str]) -> None:
        self.client = client
        self.tokens = tokens

    def sign_in(self, role: str = "reader") -> None:
        self.client.post("/ui/login", data={"token": self.tokens[role]})

    def page(self, query: str = "") -> str:
        return self.client.get(
            f"/ui/trees/{TREE}/export?tree={TREE}{query}"
        ).text


def _brief(conn: object, node_id: int, text: str, flagged: str = "") -> None:
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
        flagged=flagged,
    )


@pytest.fixture
def panel(tmp_path: Path) -> Iterator[Panel]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {"reader": create_user(conn, "rita", "reader")[1]}
    sections = [
        add_section(conn, f"{name}.py", f"{name} body\n".encode())
        for name in ("alpha", "beta", "gamma")
    ]
    cluster_store.replace_tree(
        conn,
        TREE,
        0,
        [(i, sid, False, None) for i, sid in enumerate(sections)],
        [(sid, [0.1 * (i + 1)]) for i, sid in enumerate(sections)],
    )
    leaves = [
        int(r["id"])
        for r in conn.execute(
            "SELECT id FROM nodes WHERE level = 0 ORDER BY id"
        ).fetchall()
    ]
    cluster_store.replace_level(
        conn, TREE, 1, [(0, leaf, False, None) for leaf in leaves]
    )
    root = int(
        conn.execute("SELECT id FROM nodes WHERE level = 1").fetchone()["id"]
    )
    _brief(conn, leaves[0], "# Alpha\n\nAlpha holds the signing code.")
    _brief(
        conn,
        leaves[1],
        "I can't summarise this without more context.",
        flagged="asks the caller a question",
    )
    # leaves[2] has no brief at all
    _brief(conn, root, "# Root\n\nOverview of everything.")
    conn.commit()
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        app.state.worker.stop()
        app.state.worker.join(timeout=5)
        yield Panel(client, tokens)
    conn.close()


def _links(html: str) -> list[str]:
    return [unescape(href) for href in re.findall(r'href="([^"]+)"', html)]


def test_a_reader_sees_the_shape_before_downloading(panel: Panel) -> None:
    panel.sign_in("reader")

    html = panel.page()

    assert 'aria-label="export shape"' in html
    assert re.search(r'figure num">1 / 3</div>', html)  # pages per level
    assert re.search(r'figure num">3</div>\s*<div class="label">entries', html)
    assert "files," in html
    assert f'href="/trees/{TREE}/export.zip?levels=4"' in html


def test_the_pages_read_in_place_and_their_links_work(panel: Panel) -> None:
    panel.sign_in("reader")

    root = panel.page()
    alpha = next(
        link
        for link in _links(root)
        if "page=alpha" in link and "brief" in link
    )
    child = panel.client.get(alpha).text

    assert "Overview of everything." in root
    assert "Alpha holds the signing code." in child
    section = next(link for link in _links(child) if "alpha-py" in link)
    assert "alpha body" in panel.client.get(section).text


def test_the_archive_is_the_cli_export_byte_for_byte(
    panel: Panel, tmp_path: Path
) -> None:
    panel.sign_in("reader")
    manifest = panel.client.get(f"/trees/{TREE}/export?levels=3").json()
    written, refused = _materialize(tmp_path / "cli", manifest["files"])

    answer = panel.client.get(f"/trees/{TREE}/export.zip?levels=3")
    bundle = zipfile.ZipFile(io.BytesIO(answer.content))

    assert answer.headers["content-type"] == "application/zip"
    assert not refused and written == len(bundle.namelist())
    for name in bundle.namelist():
        assert bundle.read(name) == (tmp_path / "cli" / name).read_bytes()
    assert (
        answer.content
        == panel.client.get(f"/trees/{TREE}/export.zip?levels=3").content
    )


def test_topics_without_a_usable_brief_are_flagged(panel: Panel) -> None:
    panel.sign_in("reader")

    html = panel.page()

    assert "2 topics without a usable brief" in html
    assert "asks the caller a question" in html
    assert "no brief" in html


def test_an_unbuilt_tree_gets_a_next_step(panel: Panel) -> None:
    panel.sign_in("reader")

    answer = panel.client.get("/ui/trees/empty/export?tree=empty")

    assert answer.status_code == 200
    assert "Nothing to export yet" in answer.text
    assert 'href="/ui?tree=empty"' in answer.text


def test_the_hop_limit_is_chosen_on_the_page(panel: Panel) -> None:
    panel.sign_in("reader")

    html = panel.page("&levels=2")

    assert 'name="levels" min="2" max="30" value="2"' in html
    assert f'href="/trees/{TREE}/export.zip?levels=2"' in html
    assert "hrono tree export default -o ./default-export --levels 2" in html
