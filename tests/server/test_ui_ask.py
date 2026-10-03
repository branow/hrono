"""#207: the Ask page — recall as an agent receives it, for every role."""

import hashlib
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from urllib.parse import quote, unquote

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database, open_database
from hrono.embed.op import embed
from hrono.embed.runner import EmbedError
from hrono.errors import Unavailable
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.recall import engine
from hrono.server.app import create_app
from hrono.server.ui import ask
from tests.context import job_context
from tests.tree.test_maintain import (
    fake_build,
    job,
    maintain,
    make_repo,
    register,
)

KEY = Fernet.generate_key()
TREE = "default"
ANSWERABLE = "module 7 does thing number 7"
UNANSWERABLE = "zebra"


def hashed(model_id: str) -> Callable[[list[str]], list[list[float]]]:
    """A deterministic encoder: the same text, the same vector."""

    def encode(texts: list[str]) -> list[list[float]]:
        return [
            [
                b / 255 - 0.5
                for b in hashlib.sha256(t.strip().encode()).digest()[:8]
            ]
            for t in texts
        ]

    return encode


class Distinct:
    """Writes a different brief for every topic, as a real model would."""

    def complete(self, request: CompletionRequest) -> CompletionResult:
        tag = hashlib.sha256(request.content.encode()).hexdigest()[:10]
        return CompletionResult(
            f"Topic {tag} groups modules that do related things.", Usage(4, 4)
        )


class Panel:
    def __init__(self, client: TestClient, token: str, conn: object) -> None:
        self.client = client
        self.token = token
        self.conn = conn

    def ask(self, question: str) -> str:
        self.client.post("/ui/login", data={"token": self.token})
        return self.client.get(
            f"/ui/trees/{TREE}/ask?tree={TREE}&q={quote(question)}"
        ).text


@pytest.fixture
def panel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Panel]:
    monkeypatch.chdir(tmp_path)
    url = make_repo(tmp_path / "src-repo", files=12)
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register(conn, url)
    maintain(
        job(),
        job_context(database, tmp_path),
        encoder_for=hashed,
        client=Distinct(),
        build=fake_build,
    )
    # the briefs' own passages are embedded by the next run's embed stage
    embed(job(), job_context(database, tmp_path), encoder_for=hashed)
    database.close()
    monkeypatch.setattr("hrono.recall.ask._query_encode", hashed)
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "rita", "reader")[1]
    conn.commit()
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        app.state.worker.stop()
        app.state.worker.join(timeout=5)
        yield Panel(client, token, conn)
    conn.close()


def test_a_reader_gets_passages_with_source_score_and_topic(
    panel: Panel,
) -> None:
    html = panel.ask(ANSWERABLE)

    assert 'aria-label="passages"' in html
    assert "f7.txt" in html  # the source file
    assert "bytes 0–" in html  # where in it
    assert "score 0." in html
    assert "module 7 does thing number 7" in html  # the passage itself
    assert f'href="/ui/trees/{TREE}/nodes/' in html  # the topic holding it


def test_the_page_shows_what_the_api_returns(panel: Panel) -> None:
    api = panel.client.post(
        f"/trees/{TREE}/recall",
        json={"question": ANSWERABLE},
        headers={"Authorization": f"Bearer {panel.token}"},
    ).json()

    html = panel.ask(ANSWERABLE)

    assert api["hits"]
    for hit in api["hits"]:
        assert hit["uri"].rpartition("@")[0] in html
        assert f"/nodes/{hit['topic']}?" in html


def test_a_refusal_is_a_result_with_where_to_look(panel: Panel) -> None:
    html = panel.ask(UNANSWERABLE)

    assert "Nothing here answers that confidently" in html
    assert "That is the answer an agent gets too" in html
    assert html.count(f'href="/ui/trees/{TREE}/nodes/') >= 1  # topics to try
    assert 'aria-label="passages"' not in html


def test_the_url_reproduces_the_answer(panel: Panel) -> None:
    first = panel.ask(ANSWERABLE)
    again = panel.client.get(
        f"/ui/trees/{TREE}/ask?tree={TREE}&q={quote(ANSWERABLE)}"
    ).text

    def passages(html: str) -> str:
        return html[html.index('aria-label="passages"') :]

    assert passages(first) == passages(again)


def test_the_last_questions_are_kept_to_compare(panel: Panel) -> None:
    panel.ask(ANSWERABLE)
    html = panel.ask(UNANSWERABLE)

    asked = html[html.index('aria-label="asked before"') :]
    assert asked.index(UNANSWERABLE) < asked.index(ANSWERABLE)
    assert json.loads(unquote(panel.client.cookies["hrono_asked"])) == [
        UNANSWERABLE,
        ANSWERABLE,
    ]


@pytest.mark.parametrize(
    ("failure", "says"),
    [
        pytest.param(
            Unavailable("the embedding model is still loading (m)"),
            "The embedding model is still loading",
            id="loading",
        ),
        pytest.param(
            EmbedError("sentence-transformers is not installed"),
            "pip install 'hrono[embed]'",
            id="missing",
        ),
    ],
)
def test_a_backend_that_cannot_embed_says_what_to_do(
    panel: Panel,
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    says: str,
) -> None:
    def broken(model_id: str) -> object:
        raise failure

    monkeypatch.setattr("hrono.recall.ask._query_encode", broken)

    answer = panel.client.get(f"/ui/trees/{TREE}/ask?tree={TREE}&q=x")
    html = panel.ask(ANSWERABLE)

    assert answer.status_code == 200
    assert says in html


def test_a_brief_passage_names_its_own_topic(panel: Panel) -> None:
    # the passage the brief op stored for each topic's brief (#071), rendered
    # as recall renders a hit: it belongs to the topic it summarises
    rows = panel.conn.execute(  # type: ignore[attr-defined]
        "SELECT id, source FROM passages WHERE source_type = 'node'"
    ).fetchall()

    shown = {
        engine._render(panel.conn, int(row["id"]), 0.5, TREE).topic  # noqa: SLF001
        for row in rows
    }

    assert rows
    assert shown == {int(row["source"].removeprefix("node-")) for row in rows}


def test_each_passage_is_labelled_as_what_it_is(panel: Panel) -> None:
    # a brief shown as source text would mislead whoever reads the page
    rows = panel.conn.execute(  # type: ignore[attr-defined]
        "SELECT MIN(id) AS id, source_type FROM passages GROUP BY source_type"
    ).fetchall()

    kinds = {
        row["source_type"]: ask._shown(  # noqa: SLF001
            panel.conn,
            TREE,
            engine._render(panel.conn, int(row["id"]), 0.5, TREE),  # noqa: SLF001
        )["kind"]
        for row in rows
    }

    assert kinds == {"node": "brief", "git": "source"}
    assert '<span class="chip">source</span>' in panel.ask(ANSWERABLE)


def test_the_history_keeps_only_the_newest_few(panel: Panel) -> None:
    questions = [f"question number {n}" for n in range(ask.HISTORY + 2)]
    for question in questions:
        html = panel.ask(question)

    kept = json.loads(unquote(panel.client.cookies["hrono_asked"]))
    listed = html[html.index('aria-label="asked before"') :]
    listed = listed[: listed.index("</nav>")]
    newest = list(reversed(questions))[: ask.HISTORY]
    assert kept == newest
    assert [q for q in questions if q in listed] == list(reversed(newest))


def test_a_long_history_cookie_is_read_only_as_far_as_the_cap(
    panel: Panel,
) -> None:
    # the cookie is the browser's to send: an older or edited one is input
    many = [f"old question {n}" for n in range(ask.HISTORY + 3)]
    panel.ask(ANSWERABLE)
    panel.client.cookies.set("hrono_asked", quote(json.dumps(many)))

    html = panel.client.get(f"/ui/trees/{TREE}/ask?tree={TREE}").text

    listed = html[html.index('aria-label="asked before"') :]
    listed = listed[: listed.index("</nav>")]
    assert [q for q in many if f">{q}<" in listed] == many[: ask.HISTORY]
