"""The Export page — built on request, then the shape, pages and archive."""

import io
import re
import shlex
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
from hrono.db.database import Database, open_database
from hrono.export import saved
from hrono.export.op import export
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.server.app import create_app
from hrono.server.ui.export import connect_snippets
from hrono.summarize import briefs
from hrono.tree.commands import _materialize
from tests.server.test_export_endpoint import add_section

KEY = Fernet.generate_key()
TREE = "default"


class Panel:
    def __init__(
        self, client: TestClient, tokens: dict[str, str], conn: object
    ) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn

    def export(self, levels: int = 4) -> None:
        """What pressing Export does, run here instead of by the worker."""
        export(
            Job(
                id="job_test",
                parent_id=None,
                tree=TREE,
                op="export",
                scope={"levels": levels},
                status="running",
                error=None,
                created_at="now",
                updated_at="now",
            ),
            JobContext(database=Database.adopt(self.conn)),  # type: ignore[arg-type]
        )

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
    tokens = {
        "reader": create_user(conn, "rita", "reader")[1],
        "writer": create_user(conn, "wes", "writer")[1],
    }
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
    _brief(
        conn,
        leaves[0],
        "# Alpha\n\nAlpha holds the signing code and its key rotation.",
    )
    _brief(
        conn,
        leaves[1],
        "I can't summarise this without more context.",
        flagged="asks the caller a question",
    )
    # leaves[2] has no brief at all
    _brief(
        conn,
        root,
        "# Root\n\nOverview of everything this tree holds, in brief.",
    )
    conn.commit()
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        app.state.worker.stop()
        app.state.worker.join(timeout=5)
        yield Panel(client, tokens, conn)
    conn.close()


def _links(html: str) -> list[str]:
    return [unescape(href) for href in re.findall(r'href="([^"]+)"', html)]


def test_a_reader_sees_the_shape_before_downloading(panel: Panel) -> None:
    panel.export()
    panel.sign_in("reader")

    html = panel.page()

    assert 'aria-label="export shape"' in html
    assert re.search(
        r'figure num per-level">1 / 3</div>', html
    )  # pages per level
    assert re.search(r'figure num">3</div>\s*<div class="label">entries', html)
    assert "files," in html
    assert f'href="/ui/trees/{TREE}/export.zip"' in html


def test_the_pages_read_in_place_and_their_links_work(panel: Panel) -> None:
    panel.export()
    panel.sign_in("reader")

    root = panel.page()
    alpha = next(
        link
        for link in _links(root)
        if "page=alpha" in link and "brief" in link
    )
    child = panel.client.get(alpha).text

    assert "Overview of everything this tree holds" in root
    assert "Alpha holds the signing code" in child
    assert "Sources" in child
    assert "alpha.py" in child
    assert "alpha body" not in child  # the source is named, not copied
    assert not [link for link in _links(child) if "alpha-py" in link]


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
    panel.export()
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
    panel.export(levels=2)
    panel.sign_in("writer")

    html = panel.page()

    assert 'name="levels" min="2" max="30" value="2"' in html
    assert "at 2 hops" in html
    assert "hrono tree export default -o ./default-export --levels 2" in html


def test_opening_the_page_builds_nothing(panel: Panel) -> None:
    panel.sign_in("writer")

    html = panel.page()

    assert "Not exported yet" in html
    assert ">Export</button>" in html
    assert 'id="page"' not in html
    rows = panel.conn.execute("SELECT count(*) FROM exports").fetchone()  # type: ignore[attr-defined]
    assert rows[0] == 0


def test_pressing_export_starts_a_job_and_says_so(panel: Panel) -> None:
    panel.sign_in("writer")

    answer = panel.client.post(
        f"/ui/trees/{TREE}/export",
        data={"levels": "3"},
        follow_redirects=False,
    )
    job = panel.conn.execute(  # type: ignore[attr-defined]
        "SELECT op, tree, scope FROM jobs WHERE op = 'export'"
    ).fetchone()

    assert answer.status_code == 303
    assert (job["op"], job["tree"], job["scope"]) == (
        "export",
        TREE,
        '{"levels": 3}',
    )
    html = panel.page()
    assert "Exporting" in html
    assert "disabled>Export</button>" in html


def test_a_reader_cannot_start_an_export(panel: Panel) -> None:
    panel.sign_in("reader")

    html = panel.page()
    answer = panel.client.post(
        f"/ui/trees/{TREE}/export", follow_redirects=False
    )

    assert "A writer can export" in html
    assert f'action="/ui/trees/{TREE}/export"' not in html
    assert answer.status_code in {302, 303, 401, 403}
    assert (
        panel.conn.execute(  # type: ignore[attr-defined]
            "SELECT count(*) FROM jobs WHERE op = 'export'"
        ).fetchone()[0]
        == 0
    )


def test_the_download_is_the_kept_export(panel: Panel) -> None:
    panel.export(levels=3)
    panel.sign_in("reader")

    answer = panel.client.get(f"/ui/trees/{TREE}/export.zip")
    kept = saved.load(panel.conn, TREE)  # type: ignore[arg-type]

    assert kept is not None
    assert answer.status_code == 200
    assert answer.content == kept.archive
    assert (
        answer.content
        == panel.client.get(
            f"/trees/{TREE}/export.zip?levels=3",
            headers={"Authorization": f"Bearer {panel.tokens['reader']}"},
        ).content
    )


def test_the_stored_non_briefs_are_listed_over_http(panel: Panel) -> None:
    answer = panel.client.get(
        f"/trees/{TREE}/unusable-briefs",
        headers={"Authorization": f"Bearer {panel.tokens['reader']}"},
    ).json()

    assert answer["count"] == 1
    assert answer["briefs"][0]["why"] == "asks the caller a question"


def test_connect_snippets_are_filled_and_carry_no_secret(
    panel: Panel,
) -> None:
    panel.export(levels=3)
    panel.sign_in("reader")

    html = unescape(panel.page())

    assert f"hrono profile add {TREE} --server http://testserver" in html
    assert f'hrono recall {TREE} "' in html
    # `profile add` only makes the first profile current, so each snippet
    # must switch to the pasted one before it runs a command.
    use = f"hrono profile use {TREE}"
    assert html.index(f"hrono profile add {TREE}") < html.index(use)
    assert html.index(use) < html.index(f"hrono recall {TREE}")
    assert html.count(use) == 2
    # Chained, so a profile that is not there stops the export instead of
    # running it against whichever profile was current.
    assert f"{use} && \\\nhrono tree export {TREE} -o ./{TREE}-export" in html
    assert f"curl -s -X POST http://testserver/trees/{TREE}/recall" in html
    assert f"hrono tree export {TREE} -o ./{TREE}-export --levels 3" in html
    assert f"/trees/{TREE}/export.zip?levels=3" in html
    assert html.count("Bearer YOUR_TOKEN") == 2
    assert panel.tokens["reader"] not in html
    assert 'id="connect"' in html


def test_each_snippet_url_is_a_route_a_reader_may_call(panel: Panel) -> None:
    panel.sign_in("reader")
    headers = {"Authorization": f"Bearer {panel.tokens['reader']}"}
    html = unescape(panel.page())
    recall = re.search(r"curl -s -X POST http://testserver(\S+)", html)
    export = re.search(r"curl -s '?http://testserver(\S+?)'? ", html)
    assert recall is not None and export is not None

    archive = panel.client.get(export.group(1), headers=headers)
    asked = panel.client.post(
        recall.group(1).strip("'"),
        headers=headers,
        json={"question": "signing code"},
    )

    assert archive.status_code == 200
    assert asked.status_code not in {401, 403, 404, 405, 422}


def test_connect_snippets_quote_a_tree_name_for_shell_and_url() -> None:
    name = "a&b#c'd"

    cli, http, export = (
        text for _, _, text in connect_snippets("http://h", name, 2)
    )

    assert shlex.split(cli.splitlines()[1])[3] == name
    assert "/trees/a%26b%23c%27d/recall" in http
    assert "/trees/a%26b%23c%27d/export.zip?levels=2" in export
    assert shlex.split(export.splitlines()[0].removesuffix(" && \\"))[3] == name
