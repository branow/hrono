"""The activity view over `update_log`.

The rows are written by the real writers — `propagate._record` and the
incubator — not planted, so the page's reading of "abstained" is tested
against what production actually stores rather than against an assumption.
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
        # happens to be writing when a poll lands.
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        yield Browser(client, token, conn)
    conn.close()


def test_an_empty_log_says_so(browser: Browser) -> None:
    browser.sign_in()

    assert "Nothing decided about default yet" in browser.activity()


def test_decisions_are_listed_newest_first(browser: Browser) -> None:
    browser.sign_in()
    with browser.conn:  # type: ignore[union-attr]
        record(browser.conn, TREE, 1, "none", "skipped")  # type: ignore[arg-type]
        record(browser.conn, TREE, 2, "major", "propagated", 7)  # type: ignore[arg-type]

    page = browser.activity()

    assert page.index("topic 2") < page.index("topic 1")
    assert "propagated" in page
    assert "showing 1–2 of 2" in page


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


def test_rows_are_per_tree(browser: Browser) -> None:
    browser.sign_in()
    with browser.conn:  # type: ignore[union-attr]
        record(browser.conn, TREE, 1, "major", "propagated")  # type: ignore[arg-type]

    assert "Nothing decided about other yet" in browser.activity("other")


def test_the_incubators_rows_appear_too(browser: Browser) -> None:
    # `update_log` has two writers (propagation and the incubator) and the
    # view reads one table with one shape, whatever produced the row.
    browser.sign_in()
    with browser.conn:  # type: ignore[union-attr]
        record(browser.conn, TREE, 5, "drain", "forced")  # type: ignore[arg-type]

    page = browser.activity()

    assert "drain" in page
    assert "forced" in page


def _fill(browser: Browser, count: int) -> None:
    with browser.conn:  # type: ignore[union-attr]
        for node in range(1, count + 1):
            record(browser.conn, TREE, node, "none", "skipped")  # type: ignore[arg-type]


def test_every_decision_is_reachable_by_paging(browser: Browser) -> None:
    browser.sign_in()
    _fill(browser, PAGE + 25)

    first = browser.client.get(f"/ui/trees/{TREE}/activity").text
    second = browser.client.get(f"/ui/trees/{TREE}/activity?page=2").text

    # the view is bounded and says what it is hiding: "showing 100 of 100"
    # and "showing 100 of 41,000" are different situations
    assert f"showing 1–{PAGE} of {PAGE + 25}" in first
    assert first.count("<tr") == PAGE + 1  # the rows plus the header
    assert "page 1 of 2" in first
    assert f"showing {PAGE + 1}\u2013{PAGE + 25} of {PAGE + 25}" in second
    assert second.count("<tr") == 25 + 1
    assert ">topic 25</a>" in second and ">topic 1</a>" in second
    assert ">topic 25</a>" not in first
    assert "page=2" in first and "page=1" in second


def test_a_page_past_the_end_shows_the_last(browser: Browser) -> None:
    browser.sign_in()
    _fill(browser, PAGE + 5)

    page = browser.client.get(f"/ui/trees/{TREE}/activity?page=99").text

    assert "page 2 of 2" in page


def test_filtering_by_verdict_shows_only_those_and_counts_them(
    browser: Browser,
) -> None:
    browser.sign_in()
    with browser.conn:  # type: ignore[union-attr]
        record(browser.conn, TREE, 1, "none", "skipped")  # type: ignore[arg-type]
        record(browser.conn, TREE, 2, "unparseable", "abstained")  # type: ignore[arg-type]
        record(browser.conn, TREE, 3, "major", "propagated", 9)  # type: ignore[arg-type]
        record(browser.conn, TREE, 4, "unparseable", "abstained")  # type: ignore[arg-type]

    page = browser.client.get(
        f"/ui/trees/{TREE}/activity?verdict=unparseable"
    ).text

    assert "showing 1\u20132 of 2" in page
    assert page.count('class="needs"') == 2
    assert ">topic 1</a>" not in page and ">topic 3</a>" not in page


def test_action_and_topic_filters_narrow_too(browser: Browser) -> None:
    browser.sign_in()
    with browser.conn:  # type: ignore[union-attr]
        record(browser.conn, TREE, 1, "none", "skipped")  # type: ignore[arg-type]
        record(browser.conn, TREE, 2, "none", "skipped")  # type: ignore[arg-type]
        record(browser.conn, TREE, 2, "major", "propagated", 9)  # type: ignore[arg-type]

    by_action = browser.client.get(
        f"/ui/trees/{TREE}/activity?action=skipped"
    ).text
    by_topic = browser.client.get(f"/ui/trees/{TREE}/activity?topic=2").text

    assert "of 2," in by_action
    assert "of 2," in by_topic
    assert ">topic 1</a>" not in by_topic


def test_a_filter_rides_in_the_pager_and_holds_on_page_two(
    browser: Browser,
) -> None:
    browser.sign_in()
    with browser.conn:  # type: ignore[union-attr]
        for _ in range(PAGE + 3):
            record(browser.conn, TREE, 7, "none", "skipped")  # type: ignore[arg-type]
        record(browser.conn, TREE, 8, "none", "skipped")  # type: ignore[arg-type]
        record(browser.conn, TREE, 500, "major", "propagated", 9)  # type: ignore[arg-type]

    page = browser.client.get(
        f"/ui/trees/{TREE}/activity?verdict=none&action=skipped"
    ).text

    assert "verdict=none&amp;action=skipped&amp;page=2" in page or (
        "verdict=none&action=skipped&page=2" in page
    )
    assert 'value="none" selected' in page

    first = browser.client.get(f"/ui/trees/{TREE}/activity?topic=7").text
    second = browser.client.get(
        f"/ui/trees/{TREE}/activity?topic=7&page=2"
    ).text

    assert "topic=7&amp;page=2" in first or "topic=7&page=2" in first
    assert "page 2 of 2" in second
    assert "topic 7<" in second
    assert "topic 8<" not in second


def test_a_filter_that_matches_nothing_says_so_and_keeps_the_bar(
    browser: Browser,
) -> None:
    browser.sign_in()
    _fill(browser, 3)

    page = browser.client.get(f"/ui/trees/{TREE}/activity?verdict=major").text

    assert "No decisions match" in page
    assert "Nothing decided about" not in page
    assert 'aria-label="filter decisions"' in page
    assert "<th" not in page


def test_the_reader_sees_the_same_page(browser: Browser) -> None:
    _fill(browser, PAGE + 5)
    reader = create_user(browser.conn, "ro", "reader")[1]  # type: ignore[arg-type]
    browser.client.cookies.clear()
    browser.client.post("/ui/login", data={"token": reader})

    page = browser.client.get(f"/ui/trees/{TREE}/activity?page=2").text

    assert "page 2 of 2" in page
