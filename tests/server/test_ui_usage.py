"""#203: the panel shows what was spent, and says honestly what kind of money.

State is written the way production writes it: calls through `ledger.record`
(the one writer), runs through `enqueue`, and read back through the pages.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database, open_database
from hrono.jobs import store as job_store
from hrono.jobs.worker import enqueue
from hrono.llm.ledger import Call, record
from hrono.server.app import create_app
from hrono.server.ui.usage import DAYS

KEY = Fernet.generate_key()
SONNET = "claude-sonnet-5-20260101"


class Panel:
    def __init__(self, client: TestClient, tokens: dict[str, str]) -> None:
        self.client = client
        self.tokens = tokens
        self.db: Database = client.app.state.db  # type: ignore[attr-defined]

    def as_(self, role: str) -> None:
        self.client.post("/ui/login", data={"token": self.tokens[role]})

    def run(self, op: str = "maintain", by: str = "ana") -> str:
        return enqueue(self.db, op, {}, tree="default", started_by=by)

    def call(
        self,
        run: str | None,
        *,
        provider: str = "anthropic",
        role: str = "brief",
        tokens: int = 1_000_000,
        model: str = "writer",
    ) -> None:
        record(
            self.db,
            run,
            Call(
                model=model,
                role=role,
                provider=provider,
                upstream_model=SONNET,
                input_tokens=tokens,
                output_tokens=0,
                cache_read_tokens=0,
                cache_creation_tokens=0,
                duration_ms=3_600_000,
                ok=True,
            ),
        )

    def build(self) -> None:
        with self.db.write() as conn:
            conn.execute(
                "INSERT INTO nodes(tree, level, label, created_at) "
                "VALUES ('default', 0, 0, 't')"
            )

    def get(self, path: str) -> str:
        response = self.client.get(path)
        assert response.status_code == 200, path
        return response.text


@pytest.fixture
def panel(tmp_path: Path) -> Iterator[Panel]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
    }
    conn.commit()
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        app.state.worker.stop()
        app.state.worker.join(timeout=5)
        yield Panel(client, tokens)
    conn.close()


@pytest.mark.parametrize("role", ["reader", "writer", "admin"])
def test_every_role_can_open_the_usage_page(panel: Panel, role: str) -> None:
    panel.as_(role)
    panel.call(panel.run())

    page = panel.get("/ui/usage?tree=default")

    assert "Each model" in page and "Costliest runs" in page
    assert ">Usage</a>" in page  # the tab


def test_the_page_answers_which_model_which_run_who_and_how_long(
    panel: Panel,
) -> None:
    panel.as_("reader")
    cheap, dear = panel.run("sync-tree", "bo"), panel.run("maintain", "ana")
    panel.call(cheap, tokens=1_000_000, model="small")
    panel.call(dear, tokens=5_000_000, model="big")

    page = panel.get("/ui/usage?tree=default")

    costliest = page.split('id="costliest"')[1]
    assert costliest.index(f'data-run="{dear}"') < costliest.index(
        f'data-run="{cheap}"'
    )
    assert "$10.00" in costliest and "$2.00" in costliest
    by_model = page.split('id="by-model"')[1].split("</section>")[0]
    assert 'data-model="big"' in by_model and SONNET in by_model
    assert "anthropic" in by_model
    assert by_model.count("1.00h") == 2  # an hour of model time each
    people = page.split('id="by-person"')[1]
    assert 'data-person="ana"' in people and 'data-person="bo"' in people
    assert "6,000,000 in" in page


def test_a_subscription_only_install_never_shows_money_spent(
    panel: Panel,
) -> None:
    panel.as_("reader")
    run = panel.run()
    panel.build()
    panel.call(run, provider="claude-code")

    pages = (
        panel.get("/ui/usage?tree=default"),
        panel.get("/ui?tree=default"),
        panel.get(f"/ui/jobs/{run}?tree=default"),
    )

    for page in pages:
        assert 'data-spend="metered"' not in page
        assert "estimate, not billed" in page
        assert "$2.00" in page  # the figure is there, labelled


def test_metered_spend_and_a_subscription_estimate_are_never_added(
    panel: Panel,
) -> None:
    panel.as_("reader")
    run = panel.run()
    panel.call(run, provider="anthropic")
    panel.call(run, provider="claude-code", role="condense")

    page = panel.get(f"/ui/jobs/{run}?tree=default")

    assert 'data-spend="metered">$2.00' in page
    assert "about $2.00 estimate, not billed" in page
    assert "$4.00" not in page


def test_a_run_page_splits_its_spend_by_stage(panel: Panel) -> None:
    panel.as_("reader")
    run = panel.run()
    panel.call(run, role="condense", tokens=3_000_000)
    panel.call(run, role="brief", tokens=1_000_000)

    page = panel.get(f"/ui/jobs/{run}?tree=default")

    spent = page.split('id="spend"')[1].split("</section>")[0]
    assert 'data-stage="condense"' in spent and 'data-stage="brief"' in spent
    assert "$8.00" in spent  # the total, above the split
    assert "$6.00" in spent and "$2.00" in spent


def test_a_run_from_before_the_ledger_reads_unknown_not_free(
    panel: Panel,
) -> None:
    panel.as_("reader")
    old = "old-run"
    with panel.db.write() as conn:
        job_store.insert(
            conn,
            old,
            None,
            "default",
            "maintain",
            "{}",
            "2020-01-01T00:00:00+00:00",
        )
        job_store.set_status(
            conn, old, "succeeded", None, "2020-01-01T00:05:00+00:00"
        )
    fresh = panel.run("sync-tree")
    with panel.db.write() as conn:
        job_store.set_status(
            conn, fresh, "succeeded", None, "2999-01-01T00:00:00+00:00"
        )

    before = panel.get(f"/ui/jobs/{old}?tree=default")
    after = panel.get(f"/ui/jobs/{fresh}?tree=default")

    assert 'data-spend="unknown"' in before and "no model calls" not in before
    assert 'data-spend="none"' in after and "ran before spend" not in after
    runs = panel.get("/ui/jobs?tree=default")
    assert re.search(
        r"title=\"This ran before spend was recorded\">unknown", runs
    )


def test_home_shows_the_total_and_the_last_runs_spend(panel: Panel) -> None:
    panel.as_("reader")
    panel.build()
    earlier, last = panel.run("maintain"), panel.run("sync-tree")
    panel.call(earlier, tokens=4_000_000)
    panel.call(last, tokens=1_000_000)
    with panel.db.write() as conn:
        job_store.set_status(
            conn, earlier, "succeeded", None, "2999-01-01T00:00:00+00:00"
        )
        job_store.set_status(
            conn, last, "succeeded", None, "2999-01-02T00:00:00+00:00"
        )

    page = panel.get("/ui?tree=default")

    spent = page.split('id="spent"')[1].split("</section>")[0]
    assert "$10.00" in spent  # all of it
    assert "5,000,000 in" in spent
    assert 'href="/ui/usage?tree=default"' in spent
    assert re.search(r"Last run.*?\$2\.00", spent, re.S)


def test_an_empty_tree_says_nothing_was_spent(panel: Panel) -> None:
    panel.as_("reader")

    assert "Nothing has been spent yet" in panel.get("/ui/usage?tree=default")


def test_a_run_from_before_the_ledger_keeps_the_tokens_it_knows(
    panel: Panel,
) -> None:
    panel.as_("reader")
    panel.build()
    with panel.db.write() as conn:
        job_store.insert(
            conn,
            "old-run",
            None,
            "default",
            "maintain",
            "{}",
            "2020-01-01T00:00:00+00:00",
        )
        job_store.set_status(
            conn,
            "old-run",
            "succeeded",
            None,
            "2020-01-01T00:05:00+00:00",
            result='{"tokens": {"input": 1234, "output": 56}}',
        )
    panel.run("sync-tree")

    run = panel.get("/ui/jobs/old-run?tree=default")
    head = run.split('id="run"')[0]
    section = run.split('id="spend"')[1].split("</section>")[0]

    for part in (head, section):
        assert "1,234 in, 56 out" in part
        assert 'data-spend="unknown">cost not recorded' in part
        assert "ran before spend" not in part
    home = panel.get("/ui?tree=default")
    spent = home.split('id="spent"')[1].split("</section>")[0]
    assert "1,234 in, 56 out" in spent and "cost not recorded" in spent


def test_over_time_lists_the_newest_days_oldest_first_busiest_at_full(
    panel: Panel,
) -> None:
    panel.as_("reader")
    days = DAYS + 5
    run = panel.run()
    for n in range(days):
        panel.call(run, tokens=1_000 * (n + 1))
    start = date(2026, 8, 1)
    with panel.db.write() as conn:
        for n, row in enumerate(
            conn.execute("SELECT id FROM llm_calls ORDER BY id").fetchall()
        ):
            day = start + timedelta(days=n)
            conn.execute(
                "UPDATE llm_calls SET created_at = ? WHERE id = ?",
                (f"{day}T10:00:00+00:00", row["id"]),
            )

    page = panel.get("/ui/usage?tree=default")
    shown = re.findall(r'data-day="([^"]+)"', page)
    widths = re.findall(r'<span style="width:(\d+)%">', page)

    assert len(shown) == DAYS
    assert shown == sorted(shown)
    last = start + timedelta(days=days - 1)
    first = last - timedelta(days=DAYS - 1)
    assert shown[-1] == str(last) and shown[0] == str(first)
    assert widths[-1] == "100" and int(widths[0]) < int(widths[-1])


def test_a_job_api_usage_is_keyed_by_the_job(panel: Panel) -> None:
    panel.as_("reader")
    run = panel.run()
    panel.call(run)

    body = panel.client.get(
        f"/jobs/{run}",
        headers={"Authorization": f"Bearer {panel.tokens['reader']}"},
    ).json()

    assert body["usage"]["key"] == run
