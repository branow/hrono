"""#215: the shell as a browser draws it.

Overflow and overlap are properties of laid-out pixels, so these load every
route in a real Chromium against the production app and measure. A test over
the HTML cannot fail on a 4px scrollbar, which is how every page shipped with
one.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.server.live import Live, live_server

playwright_sync = pytest.importorskip("playwright.sync_api")

WIDTHS = (800, 1100, 1440)
ROUTES = (
    "/ui",
    "/ui/trees/default/triage",
    "/ui/trees/default/graph",
    "/ui/trees/default/ask",
    "/ui/trees/default/activity",
    "/ui/jobs",
    "/ui/jobs/done-1",
    "/ui/trees/default/export",
    "/ui/config",
    "/ui/config?section=sources",
    "/ui/config?section=models",
    "/ui/guide",
    "/ui/trees/default/nodes/{leaf}",
    "/ui/trees/default/nodes/{root}",
)


@pytest.fixture(scope="module")
def live(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Live]:
    with live_server(tmp_path_factory.mktemp("live")) as server:
        yield server


@pytest.fixture(scope="module")
def browser() -> Iterator[object]:
    with playwright_sync.sync_playwright() as play:
        try:
            launched = play.chromium.launch()
        except playwright_sync.Error:
            if os.environ.get("CI"):
                raise
            pytest.skip("no chromium: run `playwright install chromium`")
        yield launched
        launched.close()


@pytest.fixture
def page(browser: object, live: Live) -> Iterator[object]:
    context = browser.new_context()  # type: ignore[attr-defined]
    context.add_cookies(
        [{"name": "hrono_token", "value": live.token, "url": live.base}]
    )
    yield context.new_page()
    context.close()


def _routes(live: Live) -> list[str]:
    ids = [
        row[0]
        for row in _query(live, "SELECT id FROM nodes ORDER BY level, id")
    ]
    return [r.format(leaf=ids[0], root=ids[-1]) for r in ROUTES]


def _query(live: Live, sql: str) -> list[tuple]:
    import sqlite3

    conn = sqlite3.connect(live.db_path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_no_route_scrolls_sideways(
    page: object, live: Live, width: int
) -> None:
    page.set_viewport_size({"width": width, "height": 900})  # type: ignore[attr-defined]
    wide = {}
    for route in _routes(live):
        page.goto(live.base + route)  # type: ignore[attr-defined]
        page.wait_for_load_state("networkidle")  # type: ignore[attr-defined]
        assert "/ui/login" not in page.url  # type: ignore[attr-defined]
        over = page.evaluate(  # type: ignore[attr-defined]
            "document.documentElement.scrollWidth - "
            "document.documentElement.clientWidth"
        )
        if over > 0:
            wide[route] = over
    assert wide == {}


HINT_ROUTES = (
    "/ui",
    "/ui/jobs",
    "/ui/config",
    "/ui/trees/default/nodes/{leaf}",
)

# A hint must open clear of the mark and of what the mark explains: the text it
# sits in and the figure above it. Read in the browser, in one place, so a hint
# that lands on a number fails here whatever stylesheet put it there.
MEASURE = """
(mark) => {
  const box = document.getElementById("tipbox");
  if (box.hidden) return {shown: false};
  const hit = (a, b) => a.left < b.right && b.left < a.right
    && a.top < b.bottom && b.top < a.bottom;
  const tip = box.getBoundingClientRect();
  const covered = [mark.getBoundingClientRect()];
  const range = document.createRange();
  range.selectNodeContents(mark.parentElement);
  covered.push(...range.getClientRects());
  const before = mark.parentElement.previousElementSibling;
  if (before && before.classList.contains("figure")) {
    covered.push(before.getBoundingClientRect());
  }
  const wide = document.documentElement.clientWidth;
  return {
    shown: true,
    inside: tip.left >= 0 && tip.right <= wide && tip.top >= 0
      && tip.bottom <= window.innerHeight,
    covers: covered.some((rect) => rect.width && hit(tip, rect)),
  };
}
"""


@pytest.mark.parametrize("width", (800, 1440))
def test_a_hint_opens_clear_of_what_it_explains_and_inside_the_window(
    page: object, live: Live, width: int
) -> None:
    page.set_viewport_size({"width": width, "height": 900})  # type: ignore[attr-defined]
    bad = []
    seen = 0
    for route in HINT_ROUTES:
        leaf = _query(live, "SELECT MIN(id) FROM nodes")[0][0]
        page.goto(live.base + route.format(leaf=leaf))  # type: ignore[attr-defined]
        for mark in page.locator("[data-tip]").all():  # type: ignore[attr-defined]
            if not mark.is_visible():
                continue
            mark.scroll_into_view_if_needed()
            mark.hover()
            result = mark.evaluate(MEASURE)
            seen += 1
            if not result["shown"] or not result["inside"] or result["covers"]:
                bad.append((route, mark.get_attribute("data-tip")[:30], result))
    assert seen > 10
    assert bad == []


@pytest.fixture
def solo(tmp_path: Path) -> Iterator[Live]:
    """A server of its own, for a test that changes what the others read."""
    with live_server(tmp_path) as server:
        yield server


def _home(page: object, live: Live) -> None:
    page.context.add_cookies(  # type: ignore[attr-defined]
        [{"name": "hrono_token", "value": live.token, "url": live.base}]
    )
    page.goto(f"{live.base}/ui")  # type: ignore[attr-defined]
    page.wait_for_load_state("load")  # type: ignore[attr-defined]


def test_home_follows_a_source_from_up_to_date_to_behind(
    page: object, solo: Live
) -> None:
    _home(page, solo)
    row = page.locator('[data-source="docs"] [data-state]')  # type: ignore[attr-defined]
    assert row.get_attribute("data-state") == "current"

    solo.advance()
    page.reload()  # type: ignore[attr-defined]

    assert row.get_attribute("data-state") == "behind"
    assert "1 of 1 source behind" in page.content()  # type: ignore[attr-defined]


def test_a_running_run_on_home_moves_without_a_reload(
    page: object, solo: Live
) -> None:
    solo.run_fanout(2)
    _home(page, solo)
    page.evaluate("window.sameDocument = true")  # type: ignore[attr-defined]
    shown = page.locator("#running .progress")  # type: ignore[attr-defined]
    assert shown.inner_text() == "0/2"

    solo.finish_piece(0)

    page.wait_for_function(  # type: ignore[attr-defined]
        "document.querySelector('#running .progress').textContent === '1/2'",
        timeout=8000,
    )
    assert page.evaluate("window.sameDocument") is True  # type: ignore[attr-defined]
