"""The dashboard's jobs view.

The runs are created through `POST /jobs` so these fail if the fan-out
breaks as well as if the page does, and every assertion is on the HTML an
operator actually receives.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.jobs import store as job_store
from hrono.registry import store as registry_store
from hrono.server.app import create_app

KEY = Fernet.generate_key()


class Browser:
    def __init__(self, client: TestClient, tokens: dict, conn: object) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn

    def sign_in(self, role: str = "admin") -> None:
        self.client.post("/ui/login", data={"token": self.tokens[role]})

    def api(self, role: str = "admin") -> dict:
        return {"Authorization": f"Bearer {self.tokens[role]}"}

    def fan_out(self) -> str:
        return str(
            self.client.post(
                "/jobs",
                json={
                    "op": "sync",
                    "scope": {"type": "all"},
                    "tree": "default",
                },
                headers=self.api(),
            ).json()["job_id"]
        )

    def page(self) -> str:
        return self.client.get("/ui/jobs?tree=default").text


@pytest.fixture
def browser(tmp_path: Path) -> Iterator[Browser]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
    }
    for name in ("alpha-src", "beta-src"):
        registry_store.insert(
            conn,
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
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        yield Browser(client, tokens, conn)
    conn.close()


def test_an_empty_tree_says_so(browser: Browser) -> None:
    browser.sign_in()

    assert "No runs for default yet" in browser.page()


def test_a_run_shows_its_status_progress_and_children(
    browser: Browser,
) -> None:
    browser.sign_in()
    parent = browser.fan_out()

    page = browser.page()

    assert f'data-job="{parent}"' in page
    assert "0/2" in page  # progress over its two children
    assert "alpha-src" in page  # the children, named by their scope
    assert "beta-src" in page
    # and the children are NOT also top-level rows: a fan-out is one run with
    # two stages, not three runs
    assert page.count("data-job=") == 1


def test_a_finished_run_shows_what_it_spent(browser: Browser) -> None:
    browser.sign_in()
    parent = browser.fan_out()
    for child in job_store.children(browser.conn, parent):  # type: ignore[arg-type]
        job_store.set_status(
            browser.conn,  # type: ignore[arg-type]
            str(child["id"]),
            "succeeded",
            None,
            "t",
            result=json.dumps({"tokens": {"input": 120, "output": 40}}),
        )

    page = browser.page()

    assert "240 in / 80 out" in page  # both children, summed
    assert "2/2" in page


def test_a_failed_run_shows_its_code_and_message(browser: Browser) -> None:
    # the error envelope's code and message are where someone reads them
    browser.sign_in()
    job_id = str(
        browser.client.post(
            "/jobs",
            json={"op": "monitor", "scope": {}, "tree": "default"},
            headers=browser.api(),
        ).json()["job_id"]
    )
    job_store.set_status(
        browser.conn,  # type: ignore[arg-type]
        job_id,
        "failed",
        "no embedding model available",
        "t",
        code="embed-error",
    )

    listed = browser.page()
    page = browser.client.get(f"/ui/jobs/{job_id}?tree=default").text

    # the list stays one line a run; the run page explains it
    assert 'data-state="failed"' in listed
    assert "The embedding model could not turn text into vectors." in page
    assert "Check the embedding model in Settings." in page
    assert "embed-error: no embedding model available" in page  # raw, kept


def test_a_live_run_is_marked_for_the_event_stream(browser: Browser) -> None:
    # EventSource is a browser built-in, so "live" costs no library — but the
    # row has to say which jobs are worth watching.
    browser.sign_in()
    parent = browser.fan_out()

    page = browser.page()

    assert f'data-job="{parent}" data-live="1"' in page
    assert "new EventSource('/jobs/' + row.dataset.job + '/events')" in page


def test_a_finished_run_is_not_watched(browser: Browser) -> None:
    browser.sign_in()
    parent = browser.fan_out()
    for child in job_store.children(browser.conn, parent):  # type: ignore[arg-type]
        job_store.set_status(
            browser.conn,
            str(child["id"]),
            "succeeded",
            None,
            "t",  # type: ignore[arg-type]
        )

    assert 'data-live="1"' not in browser.page()


def test_an_admin_can_cancel_from_the_page(browser: Browser) -> None:
    # admin, because POST /jobs/{id}/cancel is admin: a page must never take
    # a weaker role than the API for the same operation.
    browser.sign_in("admin")
    parent = browser.fan_out()

    answer = browser.client.post(
        f"/ui/jobs/{parent}/cancel?tree=default", follow_redirects=False
    )

    assert answer.status_code == 303
    assert "Stopped%202" in answer.headers["location"]
    assert [
        str(child["status"])
        for child in job_store.children(browser.conn, parent)  # type: ignore[arg-type]
    ] == ["canceled", "canceled"]


def test_a_writer_sees_no_cancel_and_is_refused_at_the_route(
    browser: Browser,
) -> None:
    # hiding it is courtesy, the route is the permission.
    # A WRITER, the strongest role the route must refuse: cancel is an
    # operator decision, exactly as the API's own cancel is.
    browser.sign_in("writer")
    parent = str(
        browser.client.post(
            "/jobs",
            json={"op": "sync", "scope": {"type": "all"}, "tree": "default"},
            headers=browser.api(),
        ).json()["job_id"]
    )

    assert ">Stop this run<" not in browser.page()
    assert (
        browser.client.post(
            f"/ui/jobs/{parent}/cancel", follow_redirects=False
        ).status_code
        == 403
    )


def test_cancelling_an_unknown_run_is_a_404(browser: Browser) -> None:
    browser.sign_in("admin")

    assert (
        browser.client.post(
            "/ui/jobs/job_nope/cancel", follow_redirects=False
        ).status_code
        == 404
    )


def test_no_token_reaches_the_page(browser: Browser) -> None:
    browser.sign_in()
    browser.fan_out()

    assert browser.tokens["admin"] not in browser.page()


def test_the_id_shown_is_the_prefix_of_the_real_one(
    browser: Browser,
) -> None:
    # short enough to read, long enough to paste into `hrono jobs get`
    browser.sign_in()
    job = browser.fan_out()

    page = browser.page()

    assert str(job).removeprefix("job_")[:8] in page
    assert f'title="{job}"' in page  # the whole id is there on hover


def test_the_running_filter_includes_a_run_with_stages_done(
    browser: Browser,
) -> None:
    # a run with some stages done is derived `partial`, which the page says as
    # `running`; filtering for what is running has to find it
    browser.sign_in()
    parent = browser.fan_out()
    first = job_store.children(browser.conn, parent)[0]  # type: ignore[arg-type]
    job_store.set_status(
        browser.conn,  # type: ignore[arg-type]
        str(first["id"]),
        "succeeded",
        None,
        "t",
    )

    page = browser.client.get("/ui/jobs?tree=default&status=running").text

    assert f'data-job="{parent}"' in page
    assert "1/2" in page
    assert 'value="partial"' not in page
