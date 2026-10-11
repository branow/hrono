"""The shell as a browser draws it.

Overflow and overlap are properties of laid-out pixels, so these load every
route in a real Chromium against the production app and measure. A test over
the HTML cannot fail on a 4px scrollbar.
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
    "/ui/trees/default/graph?view=list",
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
    """The upstream model name must not wrap onto its own line under the role.

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
        json.dumps({"name": "mine", "role": "brief", "template": "{content}"}),
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


def _focus_trail(page: object, steps: int) -> list[str]:
    """What each Tab lands on, as its tag, link target or label."""
    trail = []
    for _ in range(steps):
        page.keyboard.press("Tab")  # type: ignore[attr-defined]
        trail.append(
            page.evaluate(  # type: ignore[attr-defined]
                "(() => { const e = document.activeElement;"
                " return (e.getAttribute('href') || e.textContent || e.id)"
                ".trim().slice(0, 60); })()"
            )
        )
    return trail


def test_the_first_tab_is_a_skip_link_that_lands_on_the_content(
    page: object, live: Live
) -> None:
    page.goto(f"{live.base}/ui/trees/default/activity")  # type: ignore[attr-defined]
    page.keyboard.press("Tab")  # type: ignore[attr-defined]
    skip = page.locator("a.skip").first  # type: ignore[attr-defined]
    assert skip.evaluate("e => e === document.activeElement")
    assert skip.bounding_box()["y"] >= 0
    page.keyboard.press("Enter")  # type: ignore[attr-defined]
    assert page.evaluate("document.activeElement.id") == "content"  # type: ignore[attr-defined]


def _tab_to(page: object, probe: str, limit: int = 60) -> None:
    """Tab until `probe` (a JS expression on the active element) holds."""
    for _ in range(limit):
        page.keyboard.press("Tab")  # type: ignore[attr-defined]
        if page.evaluate(  # type: ignore[attr-defined]
            f"(e => !!e && ({probe}))(document.activeElement)"
        ):
            return
    raise AssertionError(f"Tab never reached: {probe}")


def test_slash_focuses_search_but_types_normally_inside_a_field(
    page: object, live: Live
) -> None:
    page.goto(f"{live.base}/ui/trees/default/activity")  # type: ignore[attr-defined]
    page.keyboard.press("/")  # type: ignore[attr-defined]
    box = page.locator(".finder input[name=q]")  # type: ignore[attr-defined]
    assert box.evaluate("e => e === document.activeElement")
    assert box.input_value() == ""
    page.keyboard.type("a/b")  # type: ignore[attr-defined]
    assert box.input_value() == "a/b"
    with page.expect_navigation():  # type: ignore[attr-defined]
        page.keyboard.press("Enter")  # type: ignore[attr-defined]
    assert "/find?" in page.url and "q=a%2Fb" in page.url  # type: ignore[attr-defined]


def test_the_tree_switcher_and_theme_button_work_by_keyboard(
    solo_page: object, solo: Live
) -> None:
    from hrono.db.database import open_database
    from hrono.registry import store as registry_store

    conn = open_database(solo.db_path)
    for name in ("default", "other"):
        registry_store.insert(
            conn, "trees", name, json.dumps({"name": name}), None, "t"
        )
    conn.commit()
    conn.close()
    page = solo_page
    page.goto(f"{solo.base}/ui/trees/default/activity")  # type: ignore[attr-defined]
    _tab_to(page, "e.matches('.treepick summary')")
    page.keyboard.press("Enter")  # type: ignore[attr-defined]
    assert page.locator(".treepick").get_attribute("open") is not None  # type: ignore[attr-defined]
    page.keyboard.press("Escape")  # type: ignore[attr-defined]
    assert page.locator(".treepick").get_attribute("open") is None  # type: ignore[attr-defined]
    page.keyboard.press("Enter")  # type: ignore[attr-defined]
    _tab_to(page, "e.textContent.trim() === 'other'", 4)
    with page.expect_navigation():  # type: ignore[attr-defined]
        page.keyboard.press("Enter")  # type: ignore[attr-defined]
    assert "/ui/trees/other/" in page.url  # type: ignore[attr-defined]
    _tab_to(page, "e.matches('.themer')")
    with page.expect_navigation():  # type: ignore[attr-defined]
        page.keyboard.press("Enter")  # type: ignore[attr-defined]
    assert page.locator("html").get_attribute("data-theme") in ("light", "dark")  # type: ignore[attr-defined]


def test_tab_reaches_every_topic_enter_opens_it_and_focus_is_drawn(
    page: object, live: Live
) -> None:
    page.goto(f"{live.base}/ui/trees/default/graph")  # type: ignore[attr-defined]
    page.wait_for_load_state("networkidle")  # type: ignore[attr-defined]
    topics = set(
        page.eval_on_selector_all(  # type: ignore[attr-defined]
            "svg g.node > a:first-child",
            "els => els.map(e => e.getAttribute('href'))",
        )
    )
    assert len(topics) > 1
    reached = set()
    for _ in range(80):
        page.keyboard.press("Tab")  # type: ignore[attr-defined]
        reached.add(
            page.evaluate("document.activeElement.getAttribute('href')")  # type: ignore[attr-defined]
        )
    assert topics <= reached
    # the page stays put: the header is still in view with a topic focused
    assert page.evaluate("window.scrollY") == 0  # type: ignore[attr-defined]
    assert page.locator(".topbar").bounding_box()["y"] >= 0  # type: ignore[attr-defined]
    first = sorted(topics)[0]
    for scheme in ("light", "dark"):
        page.emulate_media(color_scheme=scheme)  # type: ignore[attr-defined]
        page.reload()  # type: ignore[attr-defined]
        _tab_to(page, f"e.getAttribute('href') === {first!r}", 80)
        measured = page.evaluate(  # type: ignore[attr-defined]
            """(() => {
              const a = document.activeElement;
              const ring = getComputedStyle(a.querySelector('circle.ring'));
              const disc = getComputedStyle(a.querySelector('circle.disc'));
              return [ring.stroke, ring.strokeWidth, disc.stroke,
                      getComputedStyle(document.body).backgroundColor];
            })()"""
        )
        accent = page.evaluate(  # type: ignore[attr-defined]
            "getComputedStyle(document.documentElement)"
            ".getPropertyValue('--accent').trim()"
        )
        assert measured[0] != "none" and float(measured[1][:-2]) >= 2
        # a gap in the page colour parts the ring from the disc
        assert measured[2] == measured[3], (measured, accent)
    page.keyboard.press("Enter")  # type: ignore[attr-defined]
    page.wait_for_selector("#panel")  # type: ignore[attr-defined]
    assert page.evaluate("!!document.activeElement.closest('#panel')")  # type: ignore[attr-defined]


def test_the_wheel_zooms_the_map_about_the_cursor(
    page: object, live: Live
) -> None:
    page.set_viewport_size({"width": 1440, "height": 900})  # type: ignore[attr-defined]
    page.goto(f"{live.base}/ui/trees/default/graph")  # type: ignore[attr-defined]
    page.wait_for_load_state("networkidle")  # type: ignore[attr-defined]
    width = (
        "parseFloat(document.querySelector('#board svg').getAttribute('width'))"
    )
    box = page.locator("#board").bounding_box()  # type: ignore[attr-defined]
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)  # type: ignore[attr-defined]
    start = page.evaluate(width)  # type: ignore[attr-defined]
    page.mouse.wheel(0, -300)  # type: ignore[attr-defined]
    page.wait_for_function(f"{width} > {start}")  # type: ignore[attr-defined]
    page.mouse.wheel(0, 600)  # type: ignore[attr-defined]
    page.wait_for_function(f"{width} < {start}")  # type: ignore[attr-defined]
    # the page itself never scrolls: the wheel belongs to the map
    assert page.evaluate("window.scrollY") == 0  # type: ignore[attr-defined]


def test_the_two_views_switch_in_place_and_keep_working(
    page: object, live: Live
) -> None:
    """Switching swaps the board without a page load, the list's chevrons
    open in place, and a name opens the same panel the circles do."""
    page.set_viewport_size({"width": 1440, "height": 900})  # type: ignore[attr-defined]
    page.goto(f"{live.base}/ui/trees/default/graph?view=circles")  # type: ignore[attr-defined]
    page.wait_for_load_state("networkidle")  # type: ignore[attr-defined]
    page.evaluate("window.stayed = true")  # type: ignore[attr-defined]
    view = "document.getElementById('board').dataset.view"

    page.click("nav.seg a:has-text('List')")  # type: ignore[attr-defined]
    page.wait_for_function(f"{view} === 'list'")  # type: ignore[attr-defined]
    assert "view=list" in page.url  # type: ignore[attr-defined]
    assert page.locator("#keys, #overlays").count() == 0  # type: ignore[attr-defined]
    rows = page.locator("table.topics tbody tr").count()  # type: ignore[attr-defined]
    page.locator("table.topics a.fold.open").first.click()  # type: ignore[attr-defined]
    page.wait_for_function(  # type: ignore[attr-defined]
        f"document.querySelectorAll('table.topics tbody tr').length < {rows}"
    )
    page.locator("table.topics a.name").first.click()  # type: ignore[attr-defined]
    page.wait_for_selector("#panel")  # type: ignore[attr-defined]

    page.click("nav.seg a:has-text('Circles')")  # type: ignore[attr-defined]
    page.wait_for_function(f"{view} === 'circles'")  # type: ignore[attr-defined]
    assert page.locator("#panel").count() == 1  # type: ignore[attr-defined]
    assert page.evaluate("window.stayed === true")  # type: ignore[attr-defined]


def test_the_panel_widens_by_its_edge_and_remembers_it(
    page: object, live: Live
) -> None:
    page.set_viewport_size({"width": 1440, "height": 900})  # type: ignore[attr-defined]
    page.goto(f"{live.base}/ui/trees/default/graph")  # type: ignore[attr-defined]
    page.locator("svg g.node > a").first.click()  # type: ignore[attr-defined]
    page.wait_for_selector("#panel")  # type: ignore[attr-defined]
    wide = "document.getElementById('panel').getBoundingClientRect().width"
    start = page.evaluate(wide)  # type: ignore[attr-defined]

    grip = page.evaluate(  # type: ignore[attr-defined]
        "(() => { const r = document.getElementById('grip')"
        ".getBoundingClientRect(); return [r.left, r.top + r.height / 2]; })()"
    )
    page.mouse.move(grip[0], grip[1])  # type: ignore[attr-defined]
    page.mouse.down()  # type: ignore[attr-defined]
    page.mouse.move(grip[0] - 150, grip[1], steps=6)  # type: ignore[attr-defined]
    page.mouse.up()  # type: ignore[attr-defined]
    dragged = page.evaluate(wide)  # type: ignore[attr-defined]
    assert dragged == pytest.approx(start + 150, abs=2)

    page.focus("#grip")  # type: ignore[attr-defined]
    page.keyboard.press("ArrowRight")  # type: ignore[attr-defined]
    keyed = page.evaluate(wide)  # type: ignore[attr-defined]
    assert keyed < dragged

    page.reload()  # type: ignore[attr-defined]
    page.wait_for_selector("#panel")  # type: ignore[attr-defined]
    assert page.evaluate(wide) == pytest.approx(keyed, abs=1)  # type: ignore[attr-defined]
    # never narrower than the floor, however far it is pushed
    page.focus("#grip")  # type: ignore[attr-defined]
    page.keyboard.press("Home")  # type: ignore[attr-defined]
    assert page.evaluate(wide) >= 288  # type: ignore[attr-defined]


def test_a_hovered_topic_grows_in_place_and_no_name_has_a_halo(
    page: object, live: Live
) -> None:
    page.set_viewport_size({"width": 1440, "height": 900})  # type: ignore[attr-defined]
    page.goto(f"{live.base}/ui/trees/default/graph")  # type: ignore[attr-defined]
    page.wait_for_load_state("networkidle")  # type: ignore[attr-defined]
    disc = page.locator("circle.disc").first  # type: ignore[attr-defined]
    before = disc.bounding_box()
    disc.hover()
    page.wait_for_timeout(400)  # type: ignore[attr-defined]
    after = disc.bounding_box()

    def centre(box: dict) -> tuple[float, float]:
        return (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

    assert after["width"] > before["width"]
    assert centre(after) == pytest.approx(centre(before), abs=0.5)
    assert page.evaluate(  # type: ignore[attr-defined]
        "getComputedStyle(document.querySelector('svg text.label')).stroke"
    ) in ("none", "")


def test_the_map_has_a_skip_link_to_a_plain_list_of_topics(
    page: object, live: Live
) -> None:
    page.goto(f"{live.base}/ui/trees/default/graph")  # type: ignore[attr-defined]
    page.keyboard.press("Tab")  # type: ignore[attr-defined]
    page.keyboard.press("Tab")  # type: ignore[attr-defined]
    with page.expect_navigation():  # type: ignore[attr-defined]
        page.keyboard.press("Enter")  # type: ignore[attr-defined]
    assert "/outline" in page.url  # type: ignore[attr-defined]


def test_a_sync_starts_from_the_keyboard_alone(
    fresh_page: object, fresh: Live
) -> None:
    page = fresh_page
    page.goto(f"{fresh.base}/ui/trees/default/graph")  # type: ignore[attr-defined]
    _tab_to(page, "e.textContent.trim() === 'Start a sync'")
    with page.expect_navigation():  # type: ignore[attr-defined]
        page.keyboard.press("Enter")  # type: ignore[attr-defined]
    assert "run=job_" in page.url  # type: ignore[attr-defined]
