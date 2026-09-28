"""#186 (T54): the activity view over `update_log`.

The rows are written by the real writers — `propagate._record` and the
incubator — not planted (#176), so the page's reading of "abstained" is tested
against what production actually stores rather than against what I assumed.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.db.update_log import PAGE, record
from hrono.server.app import create_app

KEY = Fernet.generate_key()
TREE = "default"


class Browser:
    def __init__(self, client: TestClient, token: str, conn: object) -> None:
        self.client = client
        self.token = token
        self.conn = conn

    def sign_in(self) -> None:
        self.client.post("/ui/login", data={"token": self.token})

    def activity(self, tree: str = TREE) -> str:
        return self.client.get(f"/ui/trees/{tree}/activity").text


@pytest.fixture
def browser(tmp_path: Path) -> Iterator[Browser]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        # The worker polls the SAME adopted connection this fixture writes
        # through. Two threads on one sqlite connection interleave
        # transactions, which is an intermittent failure in whichever test
        # happens to be writing when a poll lands (#194).
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        yield Browser(client, token, conn)
    conn.close()


def test_an_empty_log_says_so(browser: Browser) -> None:
    browser.sign_in()

    assert "Nothing has been decided about default yet" in browser.activity()


def test_decisions_are_listed_newest_first(browser: Browser) -> None:
    browser.sign_in()
    with browser.conn:  # type: ignore[union-attr]
        record(browser.conn, TREE, 1, "none", "skipped")  # type: ignore[arg-type]
        record(browser.conn, TREE, 2, "major", "propagated", 7)  # type: ignore[arg-type]

    page = browser.activity()

    assert page.index("topic 2") < page.index("topic 1")
    assert "propagated" in page
    assert "showing 2 of 2" in page


def test_a_climb_links_to_where_it_stopped(browser: Browser) -> None:
    browser.sign_in()
    with browser.conn:  # type: ignore[union-attr]
        record(browser.conn, TREE, 2, "major", "propagated", 7)  # type: ignore[arg-type]

    page = browser.activity()

    assert f"/ui/trees/{TREE}/nodes/7" in page


def test_an_abstention_is_marked(browser: Browser) -> None:
    """The row that matters most: a topic that CHANGED and was not judged.

    `propagate._record` writes the verdict as "unparseable" and the ACTION as
    "abstained" — so reading the verdict for this would have marked nothing,
    and the page would have looked fine.
    """
    browser.sign_in()
    with browser.conn:  # type: ignore[union-attr]
        record(browser.conn, TREE, 3, "unparseable", "abstained")  # type: ignore[arg-type]
        record(browser.conn, TREE, 4, "none", "skipped")  # type: ignore[arg-type]

    page = browser.activity()

    assert page.count('class="needs"') == 1  # the abstention, and only it


def test_the_view_is_bounded_and_says_what_it_is_hiding(
    browser: Browser,
) -> None:
    # "showing 100 of 100" and "showing 100 of 41,000" are different
    # situations, and a page that shows only the first cannot tell them apart
    browser.sign_in()
    with browser.conn:  # type: ignore[union-attr]
        for node in range(PAGE + 25):
            record(browser.conn, TREE, node, "none", "skipped")  # type: ignore[arg-type]

    page = browser.activity()

    assert f"showing {PAGE} of {PAGE + 25}" in page
    assert page.count("<tr") == PAGE + 1  # the rows plus the header


def test_rows_are_per_tree(browser: Browser) -> None:
    browser.sign_in()
    with browser.conn:  # type: ignore[union-attr]
        record(browser.conn, TREE, 1, "major", "propagated")  # type: ignore[arg-type]

    assert "Nothing has been decided" in browser.activity("other")


def test_the_incubators_rows_appear_too(browser: Browser) -> None:
    # `update_log` has two writers (#087, #095) and the view reads one table
    # with one shape, whatever produced the row.
    browser.sign_in()
    with browser.conn:  # type: ignore[union-attr]
        record(browser.conn, TREE, 5, "drain", "forced")  # type: ignore[arg-type]

    page = browser.activity()

    assert "drain" in page
    assert "forced" in page
