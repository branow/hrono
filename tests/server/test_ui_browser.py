"""#215: the shell as a browser draws it.

Overflow and overlap are properties of laid-out pixels, so these load every
route in a real Chromium against the production app and measure. A test over
the HTML cannot fail on a 4px scrollbar, which is how every page shipped with
one.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.server.live import Live, live_server

playwright_sync = pytest.importorskip("playwright.sync_api")

WIDTHS = (800, 1100, 1440)
ROUTES = (
    "/ui/login",
    "/ui",
    "/ui/trees/default/triage",
    "/ui/trees/default/graph",
    "/ui/trees/default/ask",
    "/ui/trees/default/activity",
    "/ui/jobs",
    "/ui/jobs/done-1",
    "/ui/usage",
    "/ui/trees/default/export",
    "/ui/access",
    "/ui/config",
    "/ui/config?section=sources",
    "/ui/config?section=models",
    "/ui/guide",
    "/ui/trees/default/find",
    "/ui/trees/default/find?q=module",
    "/ui/trees/default/outline?open=all",
    "/ui/trees/default/files?path=f",
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
        if route != "/ui/login":
            assert "/ui/login" not in page.url  # type: ignore[attr-defined]
        over = page.evaluate(  # type: ignore[attr-defined]
            "document.documentElement.scrollWidth - "
            "document.documentElement.clientWidth"
        )
        if over > 0:
            wide[route] = over
    assert wide == {}


HINT_ROUTES = (
    "/ui/login",
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


@pytest.fixture
def fresh(tmp_path: Path) -> Iterator[Live]:
    """A server whose tree has never been built."""
    with live_server(tmp_path, built=False) as server:
        yield server


def _signed_in(browser: object, live: Live) -> Iterator[object]:
    context = browser.new_context()  # type: ignore[attr-defined]
    context.add_cookies(
        [{"name": "hrono_token", "value": live.token, "url": live.base}]
    )
    yield context.new_page()
    context.close()


# These depend on the server, so the browser closes first and its open event
# stream does not hold the server's shutdown to its timeout.
@pytest.fixture
def solo_page(browser: object, solo: Live) -> Iterator[object]:
    yield from _signed_in(browser, solo)


@pytest.fixture
def fresh_page(browser: object, fresh: Live) -> Iterator[object]:
    yield from _signed_in(browser, fresh)


def _home(page: object, live: Live) -> None:
    page.goto(f"{live.base}/ui")  # type: ignore[attr-defined]
    page.wait_for_load_state("load")  # type: ignore[attr-defined]


def test_home_follows_a_source_from_up_to_date_to_behind(
    solo_page: object, solo: Live
) -> None:
    page = solo_page
    _home(page, solo)
    row = page.locator('[data-source="docs"] [data-state]')  # type: ignore[attr-defined]
    assert row.get_attribute("data-state") == "current"

    solo.advance()
    page.reload()  # type: ignore[attr-defined]

    assert row.get_attribute("data-state") == "behind"
    assert "1 of 1 source behind" in page.content()  # type: ignore[attr-defined]


def test_a_running_run_on_home_moves_without_a_reload(
    solo_page: object, solo: Live
) -> None:
    page = solo_page
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


@pytest.mark.parametrize(
    ("route", "badge", "progress"),
    [
        ("/ui", "#running .status", "#running .progress"),
        ("/ui/jobs", "tr[data-live] .status", "tr[data-live] .progress"),
        ("/ui/jobs/going", "#run .status, .status", "#run .progress"),
    ],
)
def test_a_live_run_with_a_stage_done_reads_running_never_partial(
    solo_page: object, solo: Live, route: str, badge: str, progress: str
) -> None:
    """The streamed status turns `partial` once a stage succeeds; the badge
    updated in place must still say `running` (and paint as running)."""
    page = solo_page
    solo.run_fanout(2)
    page.goto(f"{solo.base}{route}")  # type: ignore[attr-defined]
    page.wait_for_load_state("load")  # type: ignore[attr-defined]
    shown = page.locator(badge).first  # type: ignore[attr-defined]
    assert shown.inner_text() == "running"

    solo.finish_piece(0)

    page.wait_for_function(  # type: ignore[attr-defined]
        "(sel) => /1\\s*(\\/|of)\\s*2/.test("
        "document.querySelector(sel).textContent)",
        arg=progress,
        timeout=8000,
    )
    assert shown.inner_text() == "running"
    assert shown.get_attribute("data-state") == "running"


@pytest.mark.parametrize("width", WIDTHS)
def test_the_home_of_a_tree_never_built_does_not_scroll_sideways(
    fresh_page: object, fresh: Live, width: int
) -> None:
    page = fresh_page
    page.set_viewport_size({"width": width, "height": 900})  # type: ignore[attr-defined]
    _home(page, fresh)
    assert page.locator("[data-empty]").count() == 1  # type: ignore[attr-defined]
    assert (
        page.evaluate(  # type: ignore[attr-defined]
            "document.documentElement.scrollWidth - "
            "document.documentElement.clientWidth"
        )
        <= 0
    )


def test_the_first_sync_of_an_empty_tree_moves_without_a_reload(
    fresh_page: object, fresh: Live
) -> None:
    page = fresh_page
    fresh.run_fanout(2)
    _home(page, fresh)
    page.evaluate("window.sameDocument = true")  # type: ignore[attr-defined]
    assert page.locator("#running .progress").inner_text() == "0/2"  # type: ignore[attr-defined]
    assert page.locator("button:has-text('Sync now')").count() == 0  # type: ignore[attr-defined]

    fresh.finish_piece(0)

    page.wait_for_function(  # type: ignore[attr-defined]
        "document.querySelector('#running .progress').textContent === '1/2'",
        timeout=8000,
    )
    assert page.evaluate("window.sameDocument") is True  # type: ignore[attr-defined]


@pytest.mark.parametrize("width", (800, 1440))
def test_the_guides_model_table_keeps_each_name_on_one_line(
    fresh_page: object, fresh: Live, width: int
) -> None:
    """#216: the upstream model name wrapped onto its own line under the role.

    Each cell of the role and model columns has to lay out as ONE line of
    text, at the widest and the narrowest the dashboard is read at, with the
    longest upstream name a provider hands out.
    """
    for role, kind in (
        ("condense", "text"),
        ("brief", "text"),
        ("brief-upper", "text"),
        ("judge", "text"),
        ("embedding", "embedding"),
    ):
        fresh.write(
            "INSERT INTO registry (collection, name, config, created_at, "
            "updated_at) VALUES ('models', ?, ?, 't', 't')",
            (
                f"{role}-model",
                json.dumps(
                    {
                        "name": f"{role}-model",
                        "kind": kind,
                        "role": role,
                        "model": "claude-sonnet-4-5-20250929-extended",
                    }
                ),
            ),
        )
    page = fresh_page
    page.set_viewport_size({"width": width, "height": 900})  # type: ignore[attr-defined]
    page.goto(f"{fresh.base}/ui/guide")  # type: ignore[attr-defined]

    lines = page.evaluate(  # type: ignore[attr-defined]
        """() => [...document.querySelectorAll(
          'table.roles tbody tr')].map(row => [0, 2, 3].map(index => {
            const range = document.createRange();
            range.selectNodeContents(row.children[index]);
            return new Set([...range.getClientRects()]
              .map(rect => Math.round(rect.top))).size;
          }))"""
    )

    assert len(lines) == 5
    assert lines == [[1, 1, 1]] * 5
    assert (
        page.evaluate(  # type: ignore[attr-defined]
            "document.documentElement.scrollWidth - "
            "document.documentElement.clientWidth"
        )
        <= 0
    )
