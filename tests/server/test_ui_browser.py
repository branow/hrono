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
from concurrent.futures import ThreadPoolExecutor
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
    "/ui/setup",
    "/ui/setup?step=source",
    "/ui/setup?step=build",
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


def _snippet_bars(live: Live) -> list[list[int]]:
    with playwright_sync.sync_playwright() as play:
        try:
            chrome = play.chromium.launch(
                ignore_default_args=["--hide-scrollbars"]
            )
        except playwright_sync.Error:
            if os.environ.get("CI"):
                raise
            pytest.skip("no chromium: run `playwright install chromium`")
        try:
            context = chrome.new_context(viewport={"width": 800, "height": 900})
            context.add_cookies(
                [{"name": "hrono_token", "value": live.token, "url": live.base}]
            )
            page = context.new_page()
            page.goto(f"{live.base}/ui/trees/default/export")
            page.wait_for_load_state("load")
            return page.eval_on_selector_all(
                "pre.snippet",
                "els => els.map(e => [e.scrollWidth - e.clientWidth,"
                " e.offsetHeight - e.clientHeight])",
            )
        finally:
            chrome.close()


def test_a_clipped_snippet_shows_a_scrollbar_even_where_the_system_hides_it(
    live: Live,
) -> None:
    # The module browser hides scrollbars, and a second sync playwright cannot
    # start on this thread while it runs, so this one runs on its own.
    with ThreadPoolExecutor(1) as pool:
        sizes = pool.submit(_snippet_bars, live).result()
    clipped = [bar for over, bar in sizes if over > 0]
    assert clipped, "no snippet overflows, so the check proves nothing"
    assert all(bar > 0 for bar in clipped)


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


def test_a_callout_code_span_does_not_wrap_at_1100px(
    page: object, live: Live
) -> None:
    page.set_viewport_size({"width": 1100, "height": 900})  # type: ignore[attr-defined]
    page.goto(live.base + "/ui/setup")  # type: ignore[attr-defined]
    lines = page.evaluate(  # type: ignore[attr-defined]
        """() => {
          const box = document.createElement("div");
          box.className = "callout warn";
          box.style.width = "160px";
          box.innerHTML = '<div class="body"><p class="hint">Install it with '
            + '<code>uv pip install "hrono[embed]"</code>, restart.</p></div>';
          document.querySelector("main").prepend(box);
          return box.querySelector("code").getClientRects().length;
        }"""
    )
    assert lines == 1


def test_a_diff_line_copies_without_its_marker_and_long_ones_show_gaps(
    browser: object, tmp_path: Path
) -> None:
    from hrono.db.database import open_database
    from hrono.summarize import briefs

    with live_server(tmp_path) as server:
        conn = open_database(server.db_path)
        node = conn.execute(
            "SELECT node_id FROM briefs ORDER BY node_id LIMIT 1"
        ).fetchone()[0]
        old = "\n".join(f"line {n}" for n in range(30))
        new = old.replace("line 2\n", "line two\n").replace(
            "line 27\n", "line twenty-seven\n"
        )
        for text in (old, new):
            with conn:
                briefs.upsert(
                    conn,
                    node,
                    text,
                    model_name="m",
                    prompt_name="brief",
                    prompt_hash="h",
                    member_signature="s",
                    input_tokens=1,
                    output_tokens=1,
                )
        conn.close()
        context = browser.new_context()  # type: ignore[attr-defined]
        context.add_cookies(
            [{"name": "hrono_token", "value": server.token, "url": server.base}]
        )
        page = context.new_page()
        page.goto(f"{server.base}/ui/trees/default/nodes/{node}")
        page.locator("details:has-text('kept') > summary").first.click()
        copied = page.evaluate(
            """() => {
              const line = document.querySelector('.diff-add');
              const range = document.createRange();
              range.selectNodeContents(line.parentElement);
              const sel = getSelection();
              sel.removeAllRanges();
              sel.addRange(range);
              return sel.toString();
            }"""
        )
        gaps = page.locator(".diff-gap").count()
        full = page.locator("summary:has-text('Full text')").first
        full.click()
        shown = full.locator("xpath=following-sibling::pre").inner_text()
        context.close()

    assert "+" not in copied and "-line" not in copied
    assert "line twenty-seven" in copied
    assert gaps == 3
    assert shown == old


def _topics_for_the_filter(live: Live) -> None:
    import json as _json

    from hrono.cluster import store as cluster_store
    from hrono.db.database import open_database
    from hrono.registry import store as registry_store
    from hrono.summarize import briefs
    from tests.server.live import _section

    conn = open_database(live.db_path)
    with conn:
        parent = conn.execute(
            "SELECT MAX(id) FROM nodes WHERE level = 1"
        ).fetchone()[0]
        texts = {parent: "Overview of everything"}
        for index in range(12):
            leaf = cluster_store.add_leaf_node(
                conn,
                "default",
                [(_section(conn, f"x/{index}.md", b"x"), False, None)],
            )
            texts[leaf] = f"Leaf topic {index}"
        for node, text in texts.items():
            briefs.upsert(
                conn,
                node,
                text,
                model_name="m",
                prompt_name="brief",
                prompt_hash="h",
                member_signature="s",
                input_tokens=1,
                output_tokens=1,
            )
    registry_store.insert(
        conn,
        "prompts",
        "mine",
        _json.dumps({"name": "mine", "role": "brief", "template": "{content}"}),
        None,
        "t",
    )
    conn.close()


def test_the_topic_filter_hides_empty_levels_and_resets_a_hidden_pick(
    solo_page: object, solo: Live
) -> None:
    _topics_for_the_filter(solo)
    page = solo_page
    page.goto(f"{solo.base}/ui/config?tree=default&edit=prompts:mine")  # type: ignore[attr-defined]
    pick = page.locator("#preview-topic-pick")  # type: ignore[attr-defined]
    find = page.locator("#preview-topic-find")  # type: ignore[attr-defined]

    def shown() -> list[str]:
        return pick.evaluate(
            "s => [...s.querySelectorAll('option[value]:not([value=\"\"])')]"
            ".filter(o => !o.hidden).map(o => o.textContent)"
        )

    def levels() -> list[str]:
        return pick.evaluate(
            "s => [...s.querySelectorAll('optgroup')]"
            ".filter(g => !g.hidden).map(g => g.label)"
        )

    everything = shown()
    assert len(everything) == 14
    assert levels() == ["Level 0", "Level 1"]

    find.fill("leaf topic 1")
    assert shown() == ["Leaf topic 1", "Leaf topic 10", "Leaf topic 11"]
    assert levels() == ["Level 0"]

    find.fill("overview")
    assert shown() == ["Overview of everything"]
    assert levels() == ["Level 1"]

    find.fill("")
    pick.select_option(label="Overview of everything")
    find.fill("leaf")
    assert pick.input_value() == ""
    assert levels() == ["Level 0"]

    find.fill("")
    assert shown() == everything
    assert levels() == ["Level 0", "Level 1"]


def test_a_long_dropped_out_label_stays_inside_its_row_on_a_phone(
    page: object, live: Live
) -> None:
    page.set_viewport_size({"width": 375, "height": 800})  # type: ignore[attr-defined]
    page.goto(f"{live.base}/ui/trees/default/ask")  # type: ignore[attr-defined]
    page.wait_for_load_state("load")  # type: ignore[attr-defined]
    # the page's own markup for the list, with a name that has no break
    page.evaluate(  # type: ignore[attr-defined]
        """() => {
          const s = document.createElement('section');
          s.id = 'dropped';
          s.innerHTML = '<ul><li class="mono small">#1 '
            + 'a'.repeat(80) + '.txt 4 <span class="faint">score 0.5</span>'
            + '</li></ul>';
          document.querySelector('main').appendChild(s);
        }"""
    )
    overflow = page.evaluate(  # type: ignore[attr-defined]
        """() => {
          const li = document.querySelector('#dropped li');
          const r = document.createRange();
          r.selectNodeContents(li);
          const box = li.getBoundingClientRect();
          return r.getBoundingClientRect().right - box.right;
        }"""
    )
    assert overflow <= 0
