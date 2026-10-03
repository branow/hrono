"""#215: the frame every page sits in — navigation, empty states, feedback.

Driven the way a browser drives it: real GETs and form POSTs with a real
cookie, on a database the production writers filled where one is needed.
"""

from __future__ import annotations

from collections.abc import Iterator
from html.parser import HTMLParser
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.jobs import store as job_store
from hrono.server.app import create_app
from hrono.server.ui import tabs

KEY = Fernet.generate_key()
TREE = "default"
LABELS = [
    "Home",
    "Map",
    "Find",
    "Ask",
    "Runs",
    "Health",
    "Export",
    "Usage",
    "Settings",
    "Guide",
]


class Browser:
    def __init__(self, client: TestClient, tokens: dict, conn: object) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn

    def sign_in(self, role: str = "admin") -> None:
        self.client.cookies.clear()
        self.client.post("/ui/login", data={"token": self.tokens[role]})

    def get(self, path: str) -> str:
        answer = self.client.get(path, follow_redirects=False)
        assert answer.status_code == 200, (path, answer.status_code)
        return answer.text


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
        yield Browser(client, tokens, conn)
    conn.close()


def _job(conn: object, job_id: str, status: str, **columns: str) -> str:
    job_store.insert(  # type: ignore[arg-type]
        conn, job_id, None, TREE, "sync-tree", "{}", "2026-10-03T10:00:00+00:00"
    )
    sets = ", ".join(f"{name} = ?" for name in ("status", *columns))
    with conn:  # type: ignore[attr-defined]
        conn.execute(  # type: ignore[attr-defined]
            f"UPDATE jobs SET {sets} WHERE id = ?",
            (status, *columns.values(), job_id),
        )
    return job_id


class Marked(HTMLParser):
    """Which nav tabs are the current page, and every empty state's actions."""

    def __init__(self) -> None:
        super().__init__()
        self.tabs: list[tuple[str, bool]] = []
        self.empties: list[list[str]] = []
        self._tab: dict[str, str] | None = None
        self._depth = 0
        self._text = ""

    def handle_starttag(self, tag: str, attrs: list) -> None:
        found = dict(attrs)
        classes = (found.get("class") or "").split()
        if tag == "a" and "tab" in classes:
            self._tab = found
            self._text = ""
        if "empty" in classes or "data-empty" in found:
            self.empties.append([])
            self._depth = 1
        elif self._depth:
            self._depth += 1
            if tag in ("a", "button") and "btn" in classes:
                self.empties[-1].append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._tab is not None:
            self.tabs.append(
                (self._text.strip(), self._tab.get("aria-current") == "page")
            )
            self._tab = None
        if self._depth:
            self._depth -= 1

    def handle_data(self, data: str) -> None:
        if self._tab is not None:
            self._text += data


def _read(page: str) -> Marked:
    marked = Marked()
    marked.feed(page)
    return marked


def test_the_navigation_is_the_agreed_set_of_pages_that_exist(
    browser: Browser,
) -> None:
    browser.sign_in()

    labels = [name for name, _ in _read(browser.get("/ui")).tabs]

    assert labels == [*LABELS[:-1], "Access", "Guide"]


@pytest.mark.parametrize("role", ["reader", "writer"])
def test_only_an_admin_is_offered_the_access_tab(
    browser: Browser, role: str
) -> None:
    browser.sign_in(role)

    labels = [name for name, _ in _read(browser.get("/ui")).tabs]

    assert labels == LABELS


@pytest.mark.parametrize(
    ("path", "current"),
    [
        ("/ui", "Home"),
        (f"/ui/trees/{TREE}/graph", "Map"),
        (f"/ui/trees/{TREE}/find", "Find"),
        (f"/ui/trees/{TREE}/outline", "Find"),
        (f"/ui/trees/{TREE}/files", "Find"),
        (f"/ui/trees/{TREE}/ask", "Ask"),
        ("/ui/jobs", "Runs"),
        ("/ui/jobs/finished", "Runs"),
        (f"/ui/trees/{TREE}/activity", "Runs"),
        (f"/ui/trees/{TREE}/triage", "Health"),
        (f"/ui/trees/{TREE}/export", "Export"),
        ("/ui/config", "Settings"),
        ("/ui/access", "Access"),
        ("/ui/guide", "Guide"),
    ],
)
def test_every_page_marks_exactly_its_own_tab(
    browser: Browser, path: str, current: str
) -> None:
    _job(browser.conn, "finished", "succeeded")
    browser.sign_in()

    marked = [n for n, here in _read(browser.get(path)).tabs if here]

    assert marked == [current]


def test_a_topic_page_is_not_the_map_and_says_what_it_is(
    browser: Browser,
) -> None:
    with browser.conn:  # type: ignore[attr-defined]
        browser.conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 0, 0, 't')",
            (TREE,),
        )
    browser.sign_in()

    shown = _read(browser.get(f"/ui/trees/{TREE}/nodes/1")).tabs

    assert [n for n, here in shown if here] == ["Topic"]
    assert ("Map", False) in shown


def test_the_tab_row_names_its_current_page_by_path_alone() -> None:
    assert [t["label"] for t in tabs("/ui/jobs/abc", TREE) if t["current"]] == [
        "Runs"
    ]
    assert [t["label"] for t in tabs("/ui/jobs/", TREE) if t["current"]] == [
        "Runs"
    ]
    assert [t["label"] for t in tabs("/ui/", TREE) if t["current"]] == ["Home"]
    assert [t["label"] for t in tabs("/ui/trees/x/nodes/9", "x")][2] == "Topic"
    assert "Topic" not in [t["label"] for t in tabs("/ui/trees/x/graph", "x")]


def test_the_access_tab_is_marked_on_the_pages_its_posts_draw() -> None:
    for path in ("/ui/access", "/ui/access/create", "/ui/access/rotate-key"):
        shown = tabs(path, TREE, "admin")
        assert [t["label"] for t in shown if t["current"]] == ["Access"]


EMPTY_PAGES = (
    "/ui",
    f"/ui/trees/{TREE}/graph",
    f"/ui/trees/{TREE}/activity",
    f"/ui/trees/{TREE}/export",
    "/ui/jobs",
    "/ui/guide",
    "/ui/config?section=trees",
    "/ui/config?section=sources",
)


@pytest.mark.parametrize("role", ["admin", "reader"])
@pytest.mark.parametrize("path", EMPTY_PAGES)
def test_every_empty_state_offers_a_button_not_a_command(
    browser: Browser, path: str, role: str
) -> None:
    browser.sign_in(role)

    page = browser.get(path)
    empties = _read(page).empties

    if role == "admin":
        assert empties, "this page was meant to be empty"
        assert all(actions for actions in empties), page
    assert "hrono sync" not in page
    assert "hrono sources add" not in page


def test_an_empty_overview_walks_through_the_two_steps_as_buttons(
    browser: Browser,
) -> None:
    browser.sign_in()

    page = browser.get("/ui")

    assert "/ui/config?tree=default&amp;add=sources" in page
    assert f'action="/ui/trees/{TREE}/sync"' in page


def test_the_empty_states_of_a_run_each_lead_somewhere(
    browser: Browser,
) -> None:
    _job(browser.conn, "quiet", "succeeded")
    _job(browser.conn, "stopped", "failed", error="boom")
    browser.sign_in()

    for run in ("quiet", "stopped"):
        marked = _read(browser.get(f"/ui/jobs/{run}"))
        assert marked.empties
        assert all(actions for actions in marked.empties), run


def test_a_topic_with_nothing_in_it_leads_somewhere(browser: Browser) -> None:
    with browser.conn:  # type: ignore[attr-defined]
        browser.conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 0, 0, 't')",
            (TREE,),
        )
    browser.sign_in()

    marked = _read(browser.get(f"/ui/trees/{TREE}/nodes/1"))

    assert len(marked.empties) == 3
    assert all(actions for actions in marked.empties)


def test_starting_a_sync_comes_back_saying_what_it_started(
    browser: Browser,
) -> None:
    browser.sign_in()

    sent = browser.client.post(f"/ui/trees/{TREE}/sync", follow_redirects=False)
    page = browser.get(sent.headers["location"])

    assert 'id="done"' in page
    assert "Started a sync" in page
    run = sent.headers["location"].split("run=")[1]
    # the banner's own link: the page under it may list the same run
    banner = page[
        page.index('id="done"') : page.index("</div>", page.index('id="done"'))
    ]
    assert f'href="/ui/jobs/{run}?tree={TREE}">Watch it run' in banner


def test_stopping_and_re_running_say_what_they_did(browser: Browser) -> None:
    _job(browser.conn, "going", "pending")
    _job(browser.conn, "broke", "failed", error="boom")
    browser.sign_in()

    stopped = browser.client.post(
        f"/ui/jobs/going/cancel?tree={TREE}", follow_redirects=False
    )
    again = browser.client.post(
        f"/ui/jobs/broke/retry?tree={TREE}", follow_redirects=False
    )

    assert "Stopped 1." in browser.get(stopped.headers["location"])
    assert "Started again from broke" in browser.get(again.headers["location"])


def test_an_outcome_is_said_once_on_a_page_that_used_to_say_it_itself(
    browser: Browser,
) -> None:
    browser.sign_in()

    page = browser.get("/ui/config?section=sources&done=saved+one")

    assert page.count("saved one") == 1
