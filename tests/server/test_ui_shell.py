"""#180 (T49): the dashboard shell — server-rendered, logged in, role-gated.

Every test drives the browser's own path: a real GET, a real form POST, real
cookies. The API's auth tests cover the header carrier; these cover the cookie
one, and the point of the ticket is that they are the SAME check underneath.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.registry import store as registry_store
from hrono.server.app import create_app
from hrono.server.auth import COOKIE

KEY = Fernet.generate_key()


class Browser:
    def __init__(self, client: TestClient, tokens: dict) -> None:
        self.client = client
        self.tokens = tokens

    def sign_in(self, role: str = "admin") -> object:
        return self.client.post(
            "/ui/login",
            data={"token": self.tokens[role]},
            follow_redirects=False,
        )

    def page(self, path: str = "/ui", **kwargs: object) -> object:
        return self.client.get(path, follow_redirects=False, **kwargs)  # type: ignore[arg-type]


@pytest.fixture
def browser(tmp_path: Path) -> Iterator[Browser]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
    }
    with conn:
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES ('default', 0, 0, 't')"
        )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        yield Browser(client, tokens)
    conn.close()


def test_a_tab_with_no_cookie_gets_the_login_page_not_a_401(
    browser: Browser,
) -> None:
    # a 401 in a browser tab is a dead end; the API still answers 401.
    answer = browser.page("/ui")

    assert answer.status_code == 303  # type: ignore[attr-defined]
    assert answer.headers["location"] == "/ui/login"  # type: ignore[attr-defined]


def test_the_api_still_answers_401_for_the_same_missing_credential(
    browser: Browser,
) -> None:
    assert browser.client.get("/jobs").status_code == 401


def test_signing_in_sets_a_cookie_the_page_cannot_read(
    browser: Browser,
) -> None:
    answer = browser.sign_in()

    assert answer.status_code == 303  # type: ignore[attr-defined]
    cookie = answer.headers["set-cookie"]  # type: ignore[attr-defined]
    assert "HttpOnly" in cookie  # page scripts cannot read it
    assert "SameSite=strict" in cookie  # no other site can send it
    assert browser.page("/ui").status_code == 200  # type: ignore[attr-defined]


def test_a_bad_token_is_refused_and_sets_no_cookie(browser: Browser) -> None:
    answer = browser.client.post("/ui/login", data={"token": "nope"})

    assert answer.status_code == 401
    assert "set-cookie" not in answer.headers
    assert "not accepted" in answer.text


def test_the_token_is_never_rendered_into_the_page(browser: Browser) -> None:
    browser.sign_in()

    body = browser.page("/ui").text  # type: ignore[attr-defined]

    assert browser.tokens["admin"] not in body


def test_a_reader_gets_no_write_control(browser: Browser) -> None:
    browser.sign_in("reader")

    body = browser.page("/ui").text  # type: ignore[attr-defined]

    assert "Sync now" not in body


def test_a_writer_does(browser: Browser) -> None:
    # the other half: a control that is absent for everyone is not role-gating
    browser.sign_in("writer")

    assert "Sync now" in browser.page("/ui").text  # type: ignore[attr-defined]


def test_logging_out_clears_the_cookie(browser: Browser) -> None:
    browser.sign_in()

    answer = browser.client.post("/ui/logout", follow_redirects=False)

    assert answer.status_code == 303
    assert browser.client.cookies.get(COOKIE) in (None, "")
    assert browser.page("/ui").headers["location"] == "/ui/login"  # type: ignore[attr-defined]


def test_the_switcher_lists_declared_trees(browser: Browser) -> None:
    conn = browser.client.app.state.db  # type: ignore[attr-defined]
    with conn.write() as writable:
        for name in ("alpha", "beta"):
            registry_store.insert(
                writable,
                "trees",
                name,
                json.dumps({"name": name, "sources": ["x"]}),
                None,
                "t",
            )
    browser.sign_in()

    body = browser.page("/ui").text  # type: ignore[attr-defined]

    # each tree is offered as a link that LEADS there — the switcher used to
    # be a <select> whose options were values on a form, so asserting the
    # name appeared said nothing about whether you could reach it
    for name in ("alpha", "beta"):
        assert f'href="/ui?tree={name}"' in body
    assert browser.page("/ui?tree=alpha").status_code == 200  # type: ignore[attr-defined]


def test_an_undeclared_database_still_offers_default(
    browser: Browser,
) -> None:
    # a database nobody has partitioned still has exactly one tree (#054)
    browser.sign_in()

    assert 'href="/ui?tree=default"' in browser.page("/ui").text  # type: ignore[attr-defined]


def test_the_shell_reports_what_the_chosen_tree_holds(
    browser: Browser,
) -> None:
    browser.sign_in()

    body = browser.page("/ui?tree=default").text  # type: ignore[attr-defined]

    # the shape, as the front page states it: how many topics, over how
    # many levels
    assert re.search(
        r'class="figure num">1</div>\s*<div class="label">topics', body
    )
    assert "across 1 level" in body


def test_the_write_button_actually_starts_a_sync(browser: Browser) -> None:
    # a control that renders and 404s is worse than no control (qa, 2026-09-27)
    browser.sign_in("writer")

    answer = browser.client.post(
        "/ui/trees/default/sync", follow_redirects=False
    )

    assert answer.status_code == 303
    assert answer.headers["location"] == "/ui?tree=default"
    jobs = browser.client.get(
        "/jobs", headers={"Authorization": f"Bearer {browser.tokens['admin']}"}
    ).json()
    assert [job["op"] for job in jobs] == ["sync-tree"]


def test_a_reader_posting_it_anyway_is_refused(browser: Browser) -> None:
    # hiding the button is courtesy; the route is the permission.
    browser.sign_in("reader")

    answer = browser.client.post(
        "/ui/trees/default/sync", follow_redirects=False
    )

    assert answer.status_code == 403
    jobs = browser.client.get(
        "/jobs", headers={"Authorization": f"Bearer {browser.tokens['admin']}"}
    ).json()
    assert jobs == []


def test_every_page_carries_an_icon(browser: Browser) -> None:
    """#197: without one the browser asks for /favicon.ico, gets a 404 on
    every page load, and shows a broken icon in the tab."""
    browser.sign_in()

    page = browser.client.get("/ui").text

    assert 'rel="icon"' in page


def test_switching_tree_keeps_you_on_the_page_you_are_on(
    browser: Browser,
) -> None:
    """It used to bounce you to the overview whatever you were looking at.

    Every view but one is the same question asked of a different tree, so it
    should stay put.
    """
    from hrono.server.ui import switch

    assert switch("/ui/jobs", "default", "beta") == "/ui/jobs?tree=beta"
    assert (
        switch("/ui/trees/default/triage", "default", "beta")
        == "/ui/trees/beta/triage?tree=beta"
    )


def test_switching_from_one_topic_lands_on_the_new_trees_map(
    browser: Browser,
) -> None:
    """A topic id does not exist in another tree, so carrying it over is a
    404 waiting to happen."""
    from hrono.server.ui import switch

    assert (
        switch("/ui/trees/default/nodes/7", "default", "beta")
        == "/ui/trees/beta/graph?tree=beta"
    )


def test_the_switcher_marks_the_tree_you_are_in(browser: Browser) -> None:
    browser.sign_in()

    # the <style> block carries the SELECTOR for this, so searching the whole
    # page finds the rule whether or not any element ever matches it
    markup = _without_style(browser.page("/ui").text)  # type: ignore[attr-defined]

    assert 'aria-selected="true"' in markup


def test_one_tree_is_not_offered_as_a_choice(browser: Browser) -> None:
    # a menu with one item in it is furniture, not a control
    browser.sign_in()

    assert 'data-only="1"' in browser.page("/ui").text  # type: ignore[attr-defined]


def _without_style(page: str) -> str:
    """The page as a person reads it, minus the sheet that styles it."""
    return re.sub(r"<style>.*?</style>", "", page, flags=re.S)
