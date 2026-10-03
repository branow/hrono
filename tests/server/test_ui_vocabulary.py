"""#216: one vocabulary, enforced rather than remembered.

`GLOSSARY.md` lists the words hrono does not use. This reads every page the
dashboard serves, over a tree that has something on every page, and fails on
any of those words in what a person can read: text, tooltips, titles, field
placeholders. The list is taken FROM the glossary, so adding a word there is
all it takes to ban it, and the test cannot drift from the document.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from html.parser import HTMLParser
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.cluster.incubator import park
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.jobs import store as job_store
from hrono.registry import store as registry_store
from hrono.server import failures, outcome
from hrono.server.app import create_app
from hrono.server.ui import jobs as jobs_ui
from hrono.summarize import briefs

KEY = Fernet.generate_key()
TREE = "default"
GLOSSARY = Path(__file__).parents[2] / "GLOSSARY.md"

# attributes a person reads: a tooltip, a hover title, a hint in an empty field
READ_ATTRS = frozenset(
    {"title", "data-tip", "placeholder", "aria-label", "alt"}
)
SKIPPED = frozenset({"script", "style"})
VOID = frozenset({"input", "br", "img", "meta", "link", "hr", "path", "rect"})


def banned_words() -> tuple[str, ...]:
    """The bold words under "Words we do not use" in the glossary."""
    text = GLOSSARY.read_text()
    section = text.split("## Words we do not use", 1)[1]
    return tuple(re.findall(r"^\*\*([a-z]+)\*\*", section, flags=re.M))


class Reader(HTMLParser):
    """What a person can read on a page: its text and its readable attributes.

    Two things are left out. An element marked `data-not-used`: the Guide
    names the banned words so that a person who searches for one lands on what
    replaced it, and that sentence is the only place they may appear. And
    `<code>`: an op's name (`cluster-briefs`) is the API's and the CLI's word,
    shown as the identifier it is next to a sentence that says what it does.
    """

    def __init__(self) -> None:
        super().__init__()
        self.found: list[str] = []
        self._skip: list[str] = []
        self._exempt: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        values = dict(attrs)
        exempt = "data-not-used" in values or tag == "code"
        if tag not in VOID:
            if tag in SKIPPED:
                self._skip.append(tag)
            if exempt or self._exempt:
                self._exempt.append(tag)
        if self._exempt:
            return
        for name in READ_ATTRS:
            if values.get(name):
                self.found.append(str(values[name]))

    def handle_endtag(self, tag: str) -> None:
        if self._skip and self._skip[-1] == tag:
            self._skip.pop()
        if self._exempt:
            self._exempt.pop()

    def handle_data(self, data: str) -> None:
        if not self._skip and not self._exempt and data.strip():
            self.found.append(data.strip())


def readable(html: str) -> list[str]:
    reader = Reader()
    reader.feed(html)
    return reader.found


def banned(line: str) -> bool:
    """Whether a line says a banned word. `hrono[cluster]` is the name of a
    package extra a person types, so it is not a word of the vocabulary."""
    pattern = re.compile(
        rf"\b(?:re-?)?(?:{'|'.join(banned_words())})(?:s|ed|ing)?\b", re.I
    )
    return bool(pattern.search(re.sub(r"hrono\[\w+\]", "", line)))


def offences(html: str) -> list[str]:
    return [line for line in readable(html) if banned(line)]


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


class Browser:
    def __init__(self, client: TestClient, tokens: dict, conn: object) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn
        self.paths: list[str] = []

    def sign_in(self, role: str = "admin") -> None:
        self.client.cookies.clear()
        self.client.post("/ui/login", data={"token": self.tokens[role]})


def _world(conn: object) -> list[str]:
    """A tree with something on every page: three levels, stale briefs, a
    parked section, a forced one, a topic nothing points at, a run in each
    state, and a registered source."""
    with conn:  # type: ignore[attr-defined]

        def upper(level: int) -> int:
            conn.execute(  # type: ignore[attr-defined]
                "INSERT INTO nodes(tree, level, label, created_at) "
                "VALUES (?, ?, 0, 't')",
                (TREE, level),
            )
            return int(
                conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0]  # type: ignore[attr-defined]
            )

        leaf = cluster_store.add_leaf_node(
            conn,  # type: ignore[arg-type]
            TREE,
            [(_section(conn, name), False, None) for name in ("a.md", "b.md")],
        )
        mid, root, lost = upper(1), upper(2), upper(1)
        cluster_store.add_child(
            conn, mid, leaf, attached=False, similarity=None
        )  # type: ignore[arg-type]
        cluster_store.add_child(
            conn, root, mid, attached=False, similarity=None
        )  # type: ignore[arg-type]
        cluster_store.add_member(
            conn,  # type: ignore[arg-type]
            leaf,
            _section(conn, "forced.md"),
            forced=True,
            similarity=None,
        )
        for node in (leaf, mid, root):
            briefs.upsert(
                conn,  # type: ignore[arg-type]
                node,
                f"A summary of what topic {node} holds.",
                model_name="m",
                prompt_name="brief",
                prompt_hash="h",
                member_signature="sig",
                input_tokens=1,
                output_tokens=1,
            )
        park(conn, TREE, _section(conn, "parked.md"), 1)  # type: ignore[arg-type]
        for name in ("alpha", "beta"):
            registry_store.insert(
                conn,  # type: ignore[arg-type]
                "sources",
                name,
                json.dumps(
                    {
                        "name": name,
                        "type": "git",
                        "url": f"https://ex/{name}.git",
                        "auth": None,
                    }
                ),
                None,
                "t",
            )
        job_store.create_fanout(
            conn,  # type: ignore[arg-type]
            "run_half",
            "sync",
            "{}",
            [("kid_done", "{}"), ("kid_waiting", "{}")],
            TREE,
            "t",
        )
        job_store.set_status(conn, "kid_done", "succeeded", None, "t")  # type: ignore[arg-type]
        job_store.insert(conn, "run_failed", None, TREE, "sync", "{}", "t")  # type: ignore[arg-type]
        job_store.set_status(conn, "run_failed", "failed", "boom", "t")  # type: ignore[arg-type]
        job_store.insert(conn, "run_done", None, TREE, "settle", "{}", "t")  # type: ignore[arg-type]
        job_store.set_status(
            conn,  # type: ignore[arg-type]
            "run_done",
            "succeeded",
            None,
            "t",
            result=json.dumps({"dissolved": 1, "split": 2}),
        )
    with conn:  # type: ignore[attr-defined]
        for provider in ("anthropic", "claude-code"):
            conn.execute(  # type: ignore[attr-defined]
                "INSERT INTO llm_calls (job_id, run_id, started_by, model, "
                "role, provider, upstream_model, input_tokens, "
                "output_tokens, duration_ms, ok, created_at) VALUES "
                "('run_done', 'run_done', 'admin', 'm', 'brief', ?, "
                "'claude-sonnet-5', 1000, 100, 5000, 1, 't')",
                (provider,),
            )
    return [
        "/ui?tree=default",
        "/ui/usage",
        "/ui/jobs/run_done",
        "/ui/guide",
        "/ui/config",
        "/ui/setup",
        "/ui/setup?step=source",
        "/ui/setup?step=build",
        "/ui/setup?step=connection&provider=anthropic&change=1",
        "/ui/config?add=sources",
        "/ui/config?add=connections",
        "/ui/config?add=models",
        "/ui/config?add=prompts",
        "/ui/config?add=trees",
        "/ui/config?edit=sources:alpha",
        "/ui/config?edit=models:alpha",
        "/ui/config?delete=sources:alpha",
        "/ui/config?section=sources",
        "/ui/config?section=connections",
        "/ui/config?section=models",
        "/ui/config?section=prompts",
        "/ui/config?section=trees",
        "/ui/config?section=sources&view=json",
        "/ui/config?section=models&view=json",
        "/ui/config?section=prompts&view=json",
        "/ui/jobs?tree=default",
        "/ui/jobs/run_half?tree=default",
        "/ui/jobs/run_failed?tree=default",
        "/ui/jobs/run_done?tree=default",
        f"/ui/trees/{TREE}/nodes/{leaf}?tree={TREE}",
        f"/ui/trees/{TREE}/nodes/{mid}?tree={TREE}",
        f"/ui/trees/{TREE}/nodes/{root}?tree={TREE}",
        f"/ui/trees/{TREE}/nodes/{lost}?tree={TREE}",
        f"/ui/trees/{TREE}/graph",
        f"/ui/trees/{TREE}/graph?edges=pull,proximity,propagation",
        f"/ui/trees/{TREE}/graph?edges=pull,proximity,propagation&focus={mid}",
        f"/ui/trees/{TREE}/triage",
        f"/ui/trees/{TREE}/activity",
        f"/ui/trees/{TREE}/ask",
        f"/ui/trees/{TREE}/export",
    ]


@pytest.fixture
def browser(tmp_path: Path) -> Iterator[Browser]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
    }
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        found = Browser(client, tokens, conn)
        found.paths = _world(conn)
        yield found
    conn.close()


@pytest.fixture
def empty(tmp_path: Path) -> Iterator[Browser]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {role: create_user(conn, role, role)[1] for role in ("admin",)}
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        yield Browser(client, tokens, conn)
    conn.close()


def test_the_glossary_bans_the_words_it_always_did() -> None:
    # the scan is only as good as the list it reads; an empty list passes
    # every page, so a glossary reshuffle that breaks the parse must fail here
    assert {"cluster", "chunk", "paragraph"} <= set(banned_words())


def test_the_scan_sees_a_banned_word_in_text_and_in_a_tooltip() -> None:
    assert offences("<p>3 chunks nearer</p>")
    assert offences('<span data-tip="Re-clusters what it holds">x</span>')
    assert not offences("<p>3 sections nearer</p>")
    assert not offences('<p data-not-used="1">Not used: <b>chunk</b></p>')
    assert not offences("<script>var cluster = 1;</script>")


@pytest.mark.parametrize("role", ["reader", "writer", "admin"])
def test_no_page_says_a_word_the_glossary_does_not_use(
    browser: Browser, role: str
) -> None:
    browser.sign_in(role)
    said = {}
    for path in browser.paths:
        response = browser.client.get(path)
        assert response.status_code == 200, path
        found = offences(response.text)
        if found:
            said[path] = found

    assert said == {}


def test_no_page_quotes_a_ticket_number(browser: Browser) -> None:
    # "(#191)" means nothing to the person reading a tooltip
    browser.sign_in()
    quoted = {}
    for path in browser.paths:
        found = [
            line
            for line in readable(browser.client.get(path).text)
            if re.search(r"#\d{2,}", line)
        ]
        if found:
            quoted[path] = found

    assert quoted == {}


def test_no_page_says_one_topics_or_one_sections(browser: Browser) -> None:
    browser.sign_in()
    said = {}
    for path in browser.paths:
        found = [
            line
            for line in readable(browser.client.get(path).text)
            if re.search(r"\b1 (topics|sections|runs)\b", line)
        ]
        if found:
            said[path] = found

    assert said == {}


def test_what_a_run_says_it_did_uses_no_banned_word() -> None:
    # the sentences that reach the Runs page from data, not from a template:
    # a page scan sees only the ones its fixture happens to trigger
    said = [
        *(line for pair in failures.SAID.values() for line in pair),
        *(line for pair in outcome.COUNTED.values() for line in pair),
        *outcome.MEASURED.values(),
        *(line for pair in outcome.NEXT.values() for line in pair),
        *jobs_ui.MEANS.values(),
    ]

    assert [line for line in said if banned(line)] == []


def test_a_tree_with_nothing_in_it_says_no_banned_word(empty: Browser) -> None:
    empty.sign_in()
    said = {}
    for path in ("/ui", "/ui/guide", "/ui/config", "/ui/jobs"):
        found = offences(empty.client.get(path).text)
        if found:
            said[path] = found

    assert said == {}


def test_the_login_page_says_no_banned_word(empty: Browser) -> None:
    assert offences(empty.client.get("/ui/login").text) == []


def test_a_run_still_going_reads_running_never_partial(
    browser: Browser,
) -> None:
    browser.sign_in()
    page = browser.client.get("/ui/jobs?tree=default").text
    run = browser.client.get("/ui/jobs/run_half?tree=default").text
    home = browser.client.get("/ui?tree=default").text

    for html in (page, run, home):
        assert "partial" not in " ".join(readable(html)).lower()
        assert 'data-state="partial"' not in html
    # and it says how far it has got
    assert 'data-state="running"' in page
    assert "1/2" in page


def test_a_refused_source_name_names_its_prefix_as_an_identifier(
    empty: Browser,
) -> None:
    empty.sign_in()
    response = empty.client.post(
        "/ui/config/sources/item",
        data={
            "variant": "git",
            "f.name": "node-x",
            "f.url": "https://example.com/r.git",
            "f.auth.method": "none",
        },
    )

    assert response.status_code == 200
    assert "<code>node-</code>" in response.text
    assert "is reserved for" in response.text
    assert "Value error" not in response.text
    assert offences(response.text) == []


def test_the_name_help_names_the_prefix_as_an_identifier(
    empty: Browser,
) -> None:
    empty.sign_in()
    page = empty.client.get("/ui/config?add=sources&variant=git").text

    assert "<code>node-</code>" in page
    assert offences(page) == []


def test_idents_wraps_only_the_backticked_parts_in_code() -> None:
    from hrono.server.ui import idents

    assert (
        str(idents("a `node-` is <b> for `x` and more"))
        == "a <code>node-</code> is &lt;b&gt; for <code>x</code> and more"
    )
    assert str(idents("no ticks")) == "no ticks"
    assert str(idents("one ` tick")) == "one ` tick"


def test_the_refusal_sets_only_the_prefix_as_code(empty: Browser) -> None:
    empty.sign_in()
    response = empty.client.post(
        "/ui/config/sources/item",
        data={
            "variant": "git",
            "f.name": "node-x",
            "f.url": "https://example.com/r.git",
            "f.auth.method": "none",
        },
    )

    assert re.search(
        r"<code>node-</code> is reserved for hrono&#39;s own briefs",
        response.text,
    )
