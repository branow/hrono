"""#207: the Ask page — recall as an agent receives it, for every role."""

import hashlib
import json
import re
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
from hrono.recall.brief_passages import store_brief
from hrono.recall.engine import Hit
from hrono.server.app import create_app
from hrono.server.ui import ask, ask_history
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

    def brief_hit(self) -> Hit:
        """A stored brief passage, as recall renders a hit."""
        row = self.conn.execute(  # type: ignore[attr-defined]
            "SELECT id FROM passages WHERE source_type = 'node' ORDER BY id"
        ).fetchone()
        return engine._render(self.conn, int(row["id"]), 0.5, TREE)  # noqa: SLF001

    def rebrief(self, hit: Hit, text: str, signature: str) -> Hit:
        """Store ``hit``'s brief again, as the brief op does; its new hit."""
        node = int(hit.uri.split("/")[4])
        with self.conn:  # type: ignore[attr-defined]
            store_brief(self.conn, node, text, signature)  # type: ignore[arg-type]
        row = self.conn.execute(  # type: ignore[attr-defined]
            "SELECT id FROM passages WHERE source = ? ORDER BY id",
            (f"node-{node}",),
        ).fetchone()
        return engine._render(self.conn, int(row["id"]), 0.5, TREE)  # noqa: SLF001

    def ask(self, question: str) -> str:
        self.client.post("/ui/login", data={"token": self.token})
        return self.client.get(
            f"/ui/trees/{TREE}/ask?tree={TREE}&q={quote(question)}"
        ).text


def stored(panel: Panel) -> list[dict[str, object]]:
    return json.loads(unquote(panel.client.cookies["hrono_asked"]))


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
        return "".join(re.findall(r"<pre .*?</pre>", html, re.DOTALL))

    assert passages(first)
    assert passages(first) == passages(again)


def test_the_last_questions_are_kept_to_compare(panel: Panel) -> None:
    panel.ask(ANSWERABLE)
    html = panel.ask(UNANSWERABLE)

    asked = html[html.index('aria-label="asked before"') :]
    assert asked.index(UNANSWERABLE) < asked.index(ANSWERABLE)
    assert [e["q"] for e in stored(panel)] == [UNANSWERABLE, ANSWERABLE]


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
            'uv pip install "hrono[embed]"',
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

    kept = [e["q"] for e in stored(panel)]
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


def test_the_ask_page_leaves_no_row_in_the_agent_recall_log(
    panel: Panel,
) -> None:
    def rows() -> int:
        return panel.conn.execute(  # type: ignore[attr-defined]
            "SELECT count(*) FROM recall_log"
        ).fetchone()[0]

    panel.ask(ANSWERABLE)
    assert rows() == 0

    panel.client.post(
        f"/trees/{TREE}/recall",
        json={"question": ANSWERABLE},
        headers={"Authorization": f"Bearer {panel.token}"},
    )
    assert rows() == 1
=======
def article_of(html: str, uri_path: str) -> str:
    start = html.index(uri_path)
    return html[
        html.rindex("<article", 0, start) : html.index("</article>", start)
    ]


def test_asking_again_after_an_edit_marks_new_and_dropped(
    panel: Panel,
) -> None:
    first = panel.ask(ANSWERABLE)
    assert "Compared with" not in first
    api = panel.client.post(
        f"/trees/{TREE}/recall",
        json={"question": ANSWERABLE},
        headers={"Authorization": f"Bearer {panel.token}"},
    ).json()
    top = api["hits"][0]["uri"]
    # a different passage at the top's place: a new path, not a new version
    with panel.conn:  # type: ignore[attr-defined]
        panel.conn.execute(  # type: ignore[attr-defined]
            "UPDATE passages SET uri = 'git://x/' || uri WHERE uri = ?", (top,)
        )

    html = panel.ask(ANSWERABLE)

    assert (
        "Compared with the last time you asked this: 1 new, 1 dropped" in html
    )
    moved = article_of(html, top.rpartition("@")[0])
    assert '<span class="chip accent">new</span>' in moved
    dropped = html[html.index('aria-label="dropped out"') :]
    assert "f" in dropped and "score 0." in dropped
    assert (
        html.count('<span class="chip plain">same</span>')
        == len(api["hits"]) - 1
    )


def test_a_rebrief_that_keeps_its_members_compares_as_the_same(
    panel: Panel,
) -> None:
    old = panel.brief_hit()
    before = ask_history.snapshot((old,))
    version = old.uri.rpartition("@")[2]

    new = panel.rebrief(old, old.body, version)

    assert ask_history.compare(before, (new,)).status == ("same",)


def test_a_rebrief_with_other_members_is_one_changed_passage(
    panel: Panel,
) -> None:
    old = panel.brief_hit()
    before = ask_history.snapshot((old,))

    new = panel.rebrief(old, old.body, "other-members")

    change = ask_history.compare(before, (new,))
    assert (change.status, change.dropped) == (("changed",), ())
    assert new.uri != old.uri


def test_a_rebrief_that_rewrites_the_brief_is_new_and_dropped(
    panel: Panel,
) -> None:
    old = panel.brief_hit()
    before = ask_history.snapshot((old,))

    new = panel.rebrief(old, "A rewritten brief.", "other-members")

    change = ask_history.compare(before, (new,))
    assert change.status == ("new",)
    assert [rank for rank, _ in change.dropped] == [1]


def test_the_page_marks_a_changed_passage_and_counts_it(panel: Panel) -> None:
    panel.ask(ANSWERABLE)
    top = panel.client.post(
        f"/trees/{TREE}/recall",
        json={"question": ANSWERABLE},
        headers={"Authorization": f"Bearer {panel.token}"},
    ).json()["hits"][0]["uri"]
    with panel.conn:  # type: ignore[attr-defined]
        panel.conn.execute(  # type: ignore[attr-defined]
            "UPDATE passages SET uri = ? WHERE uri = ?",
            (top.rpartition("@")[0] + "@edited", top),
        )

    html = panel.ask(ANSWERABLE)

    assert "0 new, 1 changed, 0 dropped out" in html
    changed = article_of(html, top.rpartition("@")[0])
    assert '<span class="chip warn">changed</span>' in changed
    assert 'aria-label="dropped out"' not in html


def test_a_question_asked_again_unchanged_is_all_the_same(panel: Panel) -> None:
    panel.ask(ANSWERABLE)

    html = panel.ask(ANSWERABLE)

    assert "0 new, 0 dropped out" in html
    assert 'aria-label="dropped out"' not in html
    assert '<span class="chip accent">new</span>' not in html


def test_a_question_that_is_now_refused_lists_what_dropped(
    panel: Panel, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel.ask(ANSWERABLE)
    monkeypatch.setattr(
        "hrono.recall.ask._query_encode",
        lambda model_id: lambda texts: [[0.0] * 8] * len(texts),
    )

    html = panel.ask(ANSWERABLE)

    assert "Nothing here answers that confidently" in html
    assert "0 new, " in html
    assert 'aria-label="dropped out"' in html


def test_the_page_says_the_history_lives_in_this_browser_only(
    panel: Panel,
) -> None:
    panel.client.post("/ui/login", data={"token": panel.token})

    first_visit = panel.client.get(f"/ui/trees/{TREE}/ask?tree={TREE}").text

    assert "in this browser only" in first_visit
    assert 'aria-label="asked before"' not in first_visit
    assert "in this browser only" in panel.ask(ANSWERABLE)


def _snapshot(score: str) -> str:
    return quote(f'[{{"q":"{ANSWERABLE}","r":[["a",{score},"b"]]}}]')


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("not json", id="garbage"),
        pytest.param(quote('{"q":"x"}'), id="not-a-list"),
        pytest.param(quote('[{"q":1},7,null]'), id="wrong-shapes"),
        pytest.param(
            quote(json.dumps([{"q": ANSWERABLE, "r": [["a"]]}])),
            id="bad-snapshot",
        ),
        pytest.param(
            quote(json.dumps([{"q": ANSWERABLE, "r": [["a", True, "l"]]}])),
            id="bool-score",
        ),
        pytest.param(
            _snapshot("1" + "0" * 400),
            id="huge-int-score",
        ),
        pytest.param(_snapshot("NaN"), id="nan-score"),
        pytest.param(_snapshot("Infinity"), id="inf-score"),
        pytest.param(_snapshot("1e999"), id="overflow-float"),
        pytest.param(
            quote(
                json.dumps(
                    [
                        {
                            "q": ANSWERABLE,
                            "r": [
                                [f"k{n:05}", 0.1, "label"] for n in range(300)
                            ],
                        }
                    ]
                )
            ),
            id="oversized",
        ),
    ],
)
def test_a_corrupt_or_oversized_history_is_ignored_never_a_500(
    panel: Panel, raw: str
) -> None:
    panel.client.post("/ui/login", data={"token": panel.token})
    panel.client.cookies.set("hrono_asked", raw)

    answer = panel.client.get(
        f"/ui/trees/{TREE}/ask?tree={TREE}&q={quote(ANSWERABLE)}"
    )

    assert answer.status_code == 200
    assert "Compared with" not in answer.text
    written = answer.headers["set-cookie"].split("=", 1)[1].split(";")[0]
    assert json.loads(unquote(written))[0]["q"] == ANSWERABLE


def test_a_legacy_history_of_plain_questions_still_lists(panel: Panel) -> None:
    panel.client.post("/ui/login", data={"token": panel.token})
    panel.client.cookies.set("hrono_asked", quote(json.dumps(["old one"])))

    html = panel.client.get(f"/ui/trees/{TREE}/ask?tree={TREE}").text

    assert ">old one<" in html


def hit(uri: str, start: int = 0) -> Hit:
    return Hit(uri, "chunk", uri, "b", 0.5, start, start + 10, None)


def test_compare_marks_new_moved_same_and_dropped() -> None:
    a, b, c, d = (hit(f"git://r/{n}@v") for n in "abcd")
    before = ask_history.snapshot((a, b, c))

    change = ask_history.compare(before, (b, a, d))

    assert change.status == ("moved from #2", "moved from #1", "new")
    assert [(rank, s.key) for rank, s in change.dropped] == [
        (3, ask_history.key(c))
    ]
    assert ask_history.compare(before, (a, b, c)).status == ("same",) * 3


def test_a_range_is_part_of_a_passages_identity() -> None:
    assert ask_history.key(hit("git://r/a@v", 0)) != ask_history.key(
        hit("git://r/a@v", 10)
    )


def test_a_stored_score_is_rounded_to_three_places() -> None:
    row = Hit("git://r/a@v", "chunk", "p", "b", 0.123456789, 0, 10, None)

    assert [s.score for s in ask_history.snapshot((row,))] == [0.123]


def test_a_label_is_cut_at_a_directory_boundary() -> None:
    mid = hit("git://run/src-repo/deeper/dir/f7.txt@v", 4)
    clean = hit("git://r/src-repo/deep/dir/f7.txt@v", 4)

    assert ask_history.snapshot((mid,))[0].label == "deeper/dir/f7.txt 4"
    assert (
        ask_history.snapshot((clean,))[0].label == "src-repo/deep/dir/f7.txt 4"
    )
    assert ask_history.snapshot((hit("git://r/a@v", 4),))[0].label == (
        "git://r/a 4"
    )


def test_the_same_place_under_a_new_version_is_changed_not_dropped() -> None:
    before = ask_history.snapshot((hit("git://r/a@v1"), hit("git://r/b@v1")))

    change = ask_history.compare(before, (hit("git://r/a@v2"),))

    assert change.status == ("changed",)
    assert change.dropped == ((2, before[1]),)


def test_the_written_history_always_fits_one_cookie() -> None:
    hits = tuple(hit(f"git://repo/dir/file{n}.txt@v", n) for n in range(10))
    entries = [
        ask_history.Entry(f"q{n} " + "w" * 150, ask_history.snapshot(hits))
        for n in range(ask_history.HISTORY)
    ]

    value = ask_history.write(entries)

    assert len(value) <= ask_history.MAX_COOKIE
    back = ask_history.read(value)
    assert [e.question for e in back] == [e.question for e in entries]
    assert back[0].seen == entries[0].seen  # the newest keeps its answer
    assert back[-1].seen is None  # the oldest gave its answer up first


def test_a_model_that_is_loading_does_not_erase_the_last_answer(
    panel: Panel, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel.ask(ANSWERABLE)

    def loading(model_id: str) -> object:
        raise Unavailable("the embedding model is still loading (m)")

    with monkeypatch.context() as patch:
        patch.setattr("hrono.recall.ask._query_encode", loading)
        panel.ask(ANSWERABLE)

    assert stored(panel)[0]["r"]
    assert "0 new, 0 dropped out" in panel.ask(ANSWERABLE)


def test_a_long_question_is_cut_and_still_compares(panel: Panel) -> None:
    long = ANSWERABLE + " " + "w" * 300
    panel.ask(long)

    html = panel.ask(long)

    assert len(stored(panel)[0]["q"]) == ask_history.MAX_QUESTION
    assert "Compared with" in html
>>>>>>> 3fc4a85 (feat: re-asking a past question marks each passage new, moved or the same and lists what dropped out)
