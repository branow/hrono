"""#215: the home page answers four questions.

Is the tree up to date with its sources, is anything running, does anything
need a person, what did the last run do. The remote is a real repository, the
runs are written the way the runner writes them.
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
from hrono.ingest.git_syncer import git_sync
from hrono.jobs import store as job_store
from hrono.registry import store as registry_store
from hrono.server import outcome
from hrono.server.app import create_app
from hrono.server.freshness import Heads
from hrono.server.ui.overview import RECENT_RUNS
from tests.server.repo import commit, head_of, make_repo

KEY = Fernet.generate_key()
TREE = "default"
STAMP = "2026-10-03T10:00:00+00:00"


class Browser:
    def __init__(self, client: TestClient, tokens: dict, conn: object) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn

    def sign_in(self, role: str = "admin") -> None:
        self.client.cookies.clear()
        self.client.post("/ui/login", data={"token": self.tokens[role]})

    def home(self) -> str:
        return self.client.get(f"/ui?tree={TREE}").text

    def source(self, name: str, repo: Path) -> None:
        registry_store.insert(
            self.conn,  # type: ignore[arg-type]
            "sources",
            name,
            json.dumps(
                {"name": name, "type": "git", "url": str(repo), "auth": None}
            ),
            None,
            "t",
        )
        with self.conn:  # type: ignore[attr-defined]
            self.conn.execute(  # type: ignore[attr-defined]
                "INSERT INTO source_state VALUES (?, ?, ?)",
                (name, head_of(repo), STAMP),
            )

    def run(
        self,
        job_id: str,
        status: str,
        result: object = None,
        stamp: str = STAMP,
    ) -> None:
        job_store.insert(
            self.conn,  # type: ignore[arg-type]
            job_id,
            None,
            TREE,
            "sync-tree",
            "{}",
            stamp,
        )
        with self.conn:  # type: ignore[attr-defined]
            self.conn.execute(  # type: ignore[attr-defined]
                "UPDATE jobs SET status = ?, result = ? WHERE id = ?",
                (
                    status,
                    None if result is None else json.dumps(result),
                    job_id,
                ),
            )


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
            "VALUES (?, 0, 0, 't')",
            (TREE,),
        )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    app.state.heads = Heads(fresh_for=0.0)
    with TestClient(app) as client:
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        yield Browser(client, tokens, conn)
    conn.close()


def _row(page: str, name: str) -> str:
    start = page.index(f'data-source="{name}"')
    return page[start : page.index("</tr>", start)]


def test_a_source_that_is_behind_shows_as_behind(
    browser: Browser, tmp_path: Path
) -> None:
    repo = make_repo(tmp_path / "r")
    browser.source("docs", repo)
    commit(repo, "two")
    browser.sign_in()

    page = browser.home()

    assert 'data-state="behind"' in _row(page, "docs")
    assert "1 of 1 source behind" in page


def test_a_source_at_the_remotes_commit_is_up_to_date_and_says_where(
    browser: Browser, tmp_path: Path
) -> None:
    repo = make_repo(tmp_path / "r")
    browser.source("docs", repo)
    browser.sign_in()

    page = browser.home()

    assert 'data-state="current"' in _row(page, "docs")
    assert head_of(repo)[:8] in _row(page, "docs")
    assert "03 Oct 10:00" in _row(page, "docs")
    assert "up to date with every source" in page


def test_each_source_has_its_own_row(browser: Browser, tmp_path: Path) -> None:
    old, new = make_repo(tmp_path / "old"), make_repo(tmp_path / "new")
    browser.source("old", old)
    browser.source("new", new)
    commit(old, "two")
    browser.sign_in()

    page = browser.home()

    assert 'data-state="behind"' in _row(page, "old")
    assert 'data-state="current"' in _row(page, "new")
    assert "1 of 2 sources behind" in page


def test_home_counts_only_the_sources_the_tree_is_built_from(
    browser: Browser, tmp_path: Path
) -> None:
    mine, other = make_repo(tmp_path / "mine"), make_repo(tmp_path / "other")
    browser.source("docs", mine)
    browser.source("other", other)
    registry_store.insert(
        browser.conn,  # type: ignore[arg-type]
        "trees",
        TREE,
        json.dumps({"name": TREE, "sources": ["docs"]}),
        None,
        "t",
    )
    commit(other, "two")
    browser.sign_in()

    page = browser.home()

    assert 'data-source="other"' not in page
    assert "up to date with every source" in page


def test_a_commit_pinned_by_the_real_sync_reads_as_up_to_date_then_behind(
    browser: Browser, tmp_path: Path
) -> None:
    # the pin comes from git_sync's own `rev-parse HEAD`, the remote's from
    # `ls-remote`: the seam between them is what home's verdict rests on
    repo = make_repo(tmp_path / "r")
    browser.source("docs", repo)
    browser.sign_in()

    def read() -> None:
        pinned = git_sync(
            {"name": "docs", "url": str(repo), "auth": None},
            tmp_path / "cache",
            60.0,
        )
        with browser.conn:  # type: ignore[attr-defined]
            browser.conn.execute(  # type: ignore[attr-defined]
                "UPDATE source_state SET version = ? WHERE source = 'docs'",
                (pinned,),
            )

    read()
    assert 'data-state="current"' in _row(browser.home(), "docs")
    commit(repo, "two")
    assert 'data-state="behind"' in _row(browser.home(), "docs")
    read()
    assert 'data-state="current"' in _row(browser.home(), "docs")


def test_no_sources_offers_a_button_to_add_one(browser: Browser) -> None:
    browser.sign_in()

    page = browser.home()

    assert "No sources registered" in page
    assert "add=sources" in page


def test_a_running_run_is_on_home_and_wired_to_the_event_stream(
    browser: Browser,
) -> None:
    browser.run("job_going", "running")
    browser.sign_in()

    page = browser.home()

    assert 'id="running"' in page
    assert 'data-job="job_going"' in page
    assert "/jobs/' + row.dataset.job + '/events" in page


def test_nothing_running_says_so(browser: Browser) -> None:
    browser.run("job_done", "succeeded")
    browser.sign_in()

    page = browser.home()

    assert "Nothing is running." in page
    assert "data-live" not in page.split("<script>")[0]


def test_the_last_run_says_what_it_did(browser: Browser) -> None:
    result = {"sections": 3, "fetched": 1, "filed": 3}
    browser.run("job_done", "succeeded", result)
    browser.sign_in()

    page = browser.home()
    last = page[page.index("<h2>Last run</h2>") :]

    assert "sync-tree" in last
    assert "succeeded" in last
    assert "/ui/jobs/job_done" in last
    said = outcome.read(result).did
    assert said, "the fixture must be a result that says something"
    assert all(line in last for line in said)


def test_the_last_run_is_the_last_one_that_finished_not_the_one_going(
    browser: Browser,
) -> None:
    browser.run("job_old", "failed", stamp="2026-10-03T09:00:00+00:00")
    browser.run("job_going", "running", stamp="2026-10-03T10:00:00+00:00")
    browser.sign_in()

    page = browser.home()
    last = page[page.index("<h2>Last run</h2>") :]

    assert "/ui/jobs/job_old" in last
    assert "/ui/jobs/job_going" not in last


def test_the_map_is_a_link_in_the_head_not_a_card_of_its_own(
    browser: Browser,
) -> None:
    browser.sign_in()

    page = browser.home()

    assert page.count("Open the map") == 1
    assert "<h2>Map" not in page


def test_a_reader_sees_the_four_answers_and_no_sync_button(
    browser: Browser, tmp_path: Path
) -> None:
    browser.source("docs", make_repo(tmp_path / "r"))
    browser.sign_in("reader")

    page = browser.home()

    assert "<h2>Sources" in page
    assert "<h2>Last run</h2>" in page
    assert "/sync" not in page


def test_a_finished_fan_out_run_reads_its_derived_status_not_pending(
    browser: Browser,
) -> None:
    # #203: the parent row is stored `pending` and is never updated; its
    # status is its children's, derived at read time.
    browser.run("job_parent", "pending")
    for index in range(2):
        job_store.insert(
            browser.conn,  # type: ignore[arg-type]
            f"job_kid{index}",
            "job_parent",
            TREE,
            "sync",
            "{}",
            STAMP,
        )
        job_store.set_status(
            browser.conn,  # type: ignore[arg-type]
            f"job_kid{index}",
            "succeeded",
            None,
            STAMP,
        )
    browser.sign_in()

    page = browser.home()
    last = page[page.index("<h2>Last run</h2>") :]

    assert 'data-state="succeeded"' in last
    assert 'data-state="pending"' not in last


def test_home_reads_only_the_runs_it_shows(browser: Browser) -> None:
    for n in range(400):
        browser.run(f"job_{n:04d}", "succeeded", stamp=f"2026-10-03T{n:05d}")
    browser.sign_in()
    statements: list[str] = []
    browser.conn.set_trace_callback(statements.append)  # type: ignore[attr-defined]

    browser.home()
    browser.conn.set_trace_callback(None)  # type: ignore[attr-defined]

    asked = [s for s in statements if "FROM jobs" in s]
    bounds = [
        int(m.group(1)) for s in asked if (m := re.search(r"LIMIT (\d+)", s))
    ]
    # The bound the roots query carries is what it reads: a query with no
    # LIMIT, or one far above RECENT_RUNS, reads every run of the tree.
    assert bounds, f"no bounded jobs query among {asked[:2]}"
    assert max(bounds) == RECENT_RUNS, f"limits {bounds}"
    assert all("LIMIT" in s for s in asked if "parent_id IS NULL" in s)
