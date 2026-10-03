"""#213: a run says what it did, what failed and where, and can be retried."""

import json
import time
from collections.abc import Iterator
from functools import partial
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

import hrono
from hrono.auth.users import create_user
from hrono.cluster import ClusterError
from hrono.cluster.build import ClusterResult
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database, open_database
from hrono.errors import AppError, DomainError
from hrono.jobs import store as job_store
from hrono.jobs.model import to_job
from hrono.jobs.worker import Worker, enqueue
from hrono.llm.client import (
    CompletionRequest,
    CompletionResult,
    LLMError,
    Usage,
)
from hrono.paths import cache_root
from hrono.server.app import create_app
from hrono.server.failures import SAID
from hrono.tree.maintain import maintain
from tests.tree.test_maintain import (
    fake_build,
    fake_encoder,
    make_repo,
    register,
)

KEY = Fernet.generate_key()


class Writing:
    """Writes every summary, except for one file's section, where it fails."""

    def __init__(self, refuse: str | None = None) -> None:
        self.refuse = refuse

    def complete(self, request: CompletionRequest) -> CompletionResult:
        if self.refuse and self.refuse in request.content:
            raise LLMError("claude-code refused the call: error_max_turns")
        return CompletionResult(
            "This topic covers the module's API and how its parts fit.",
            Usage(4, 4),
        )


def _broken(vectors: object, *, init: object = None) -> ClusterResult:
    raise ClusterError("the reduction failed on these vectors")


def _run(tmp_path: Path, **seams: object) -> tuple[Database, str]:
    """A maintain through the REAL worker: its own result and failure paths."""
    database = Database.at(tmp_path / "hrono.db")
    job_id = enqueue(database, "maintain", {}, tree="default", started_by="ana")
    worker = Worker(
        database,
        ops={"maintain": partial(maintain, encoder_for=fake_encoder, **seams)},
        cache_root=cache_root(tmp_path / "hrono.db"),
    )
    worker.start()
    deadline = time.monotonic() + 60
    try:
        while time.monotonic() < deadline:
            with database.connect() as conn:
                status = job_store.get(conn, job_id)["status"]
            if status in ("succeeded", "failed"):
                break
            time.sleep(0.05)
    finally:
        worker.stop()
        worker.join(timeout=10)
    return database, job_id


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    url = make_repo(tmp_path / "src-repo", files=9)
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register(conn, url)
    database.close()
    return tmp_path


class Panel:
    def __init__(self, client: TestClient, tokens: dict[str, str]) -> None:
        self.client = client
        self.tokens = tokens

    def as_(self, role: str) -> None:
        self.client.post("/ui/login", data={"token": self.tokens[role]})


@pytest.fixture
def panel(repo: Path) -> Iterator[Panel]:
    conn = open_database(repo / "hrono.db")
    reconcile(conn, KEY)
    tokens = {r: create_user(conn, r, r)[1] for r in ("writer", "admin")}
    conn.commit()
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        app.state.worker.stop()
        app.state.worker.join(timeout=5)
        yield Panel(client, tokens)
    conn.close()


def test_every_error_code_has_a_sentence() -> None:
    import pkgutil

    for module in pkgutil.walk_packages(hrono.__path__, "hrono."):
        __import__(module.name)

    def codes(base: type) -> set[str]:
        # hrono's own classes: a test may define one of its own to raise
        own = base.__module__.startswith("hrono.")
        found = {base.code} if own else set()  # type: ignore[attr-defined]
        for sub in base.__subclasses__():
            found |= codes(sub)
        return found

    missing = (codes(AppError) | codes(DomainError)) - set(SAID)
    assert not missing, f"error codes with no sentence: {sorted(missing)}"


def test_a_successful_maintain_reports_each_stage(repo: Path) -> None:
    database, job_id = _run(repo, client=Writing(), build=fake_build)

    with database.connect() as conn:
        job = to_job(job_store.get(conn, job_id))
    stages = job.result["stages"]  # type: ignore[index]

    assert job.status == "succeeded"
    assert [s["op"] for s in stages] == [
        "sync",
        "split",
        "embed",
        "condense",
        "cluster",
        "brief",
        "build-tree",
        "embed",
    ]
    assert all(s["seconds"] >= 0 for s in stages)
    assert stages[3]["result"]["condensed"] == 9
    assert job.result["tree"]["topics_added"] > 0  # type: ignore[index]


def test_a_failed_maintain_names_the_stage_and_keeps_what_finished(
    repo: Path,
) -> None:
    database, job_id = _run(repo, client=Writing(), build=_broken)

    with database.connect() as conn:
        job = to_job(job_store.get(conn, job_id))

    assert job.status == "failed"
    assert job.error_code == "cluster-error"
    assert job.error_details["stage"] == "cluster"  # type: ignore[index]
    assert [s["op"] for s in job.result["stages"]] == [  # type: ignore[index]
        "sync",
        "split",
        "embed",
        "condense",
    ]


def test_a_failure_names_the_section_it_was_on(repo: Path) -> None:
    database, job_id = _run(
        repo, client=Writing("module 4 does"), build=fake_build
    )

    with database.connect() as conn:
        job = to_job(job_store.get(conn, job_id))

    assert job.error_code == "llm-error"
    assert job.error_details["stage"] == "condense"  # type: ignore[index]
    assert job.error_details["item"] == "section f4.txt"  # type: ignore[index]


def test_the_run_page_explains_a_failure_and_offers_a_retry(
    repo: Path, panel: Panel
) -> None:
    _database, job_id = _run(repo, client=Writing(), build=_broken)
    panel.as_("writer")

    page = panel.client.get(f"/ui/jobs/{job_id}?tree=default").text

    assert "Failed at cluster" in page
    assert "Grouping sections into topics failed." in page
    assert "pip install &#39;hrono[cluster]&#39;" in page
    assert "cluster-error: the reduction failed" in page  # the raw error
    assert 'id="stages"' in page and "<code>condense</code>" in page
    assert "Run it again" in page
    assert "only what failed or was never reached costs anything" in page


def test_a_failed_run_never_says_it_had_nothing_to_change(
    repo: Path, panel: Panel
) -> None:
    _database, job_id = _run(
        repo, client=Writing("module 4 does"), build=fake_build
    )
    panel.as_("writer")

    page = panel.client.get(f"/ui/jobs/{job_id}?tree=default").text

    assert "Failed at condense" in page
    assert "Nothing to change" not in page
    assert "makes no model calls" not in page
    assert "It stopped before it finished" in page
    assert "What finished first is in the stages above" in page


@pytest.mark.parametrize(
    ("status", "says"),
    [
        pytest.param("failed", "It stopped before it finished", id="failed"),
        pytest.param(
            "canceled", "It stopped before it finished", id="canceled"
        ),
        pytest.param("succeeded", "Nothing to change", id="succeeded"),
    ],
)
def test_only_a_finished_run_reads_as_quiet(
    repo: Path, panel: Panel, status: str, says: str
) -> None:
    database = Database.at(repo / "hrono.db")
    job_id = enqueue(database, "maintain", {}, tree="default")
    stages = json.dumps(
        {
            "stages": [
                {"op": "sync", "over": None, "seconds": 0.1, "result": None}
            ]
        }
    )
    with database.write() as conn:
        job_store.set_status(conn, job_id, status, None, "t", result=stages)
    database.close()
    panel.as_("writer")

    page = panel.client.get(f"/ui/jobs/{job_id}?tree=default").text

    assert says in page
    assert ("Nothing to change" in page) is (status == "succeeded")


def test_a_retry_runs_the_same_thing_again(repo: Path, panel: Panel) -> None:
    database, job_id = _run(repo, client=Writing(), build=_broken)
    panel.as_("writer")

    answer = panel.client.post(
        f"/ui/jobs/{job_id}/retry?tree=default", follow_redirects=False
    )

    again = answer.headers["location"].split("/ui/jobs/")[1].split("?")[0]
    with database.connect() as conn:
        first = to_job(job_store.get(conn, job_id))
        second = to_job(job_store.get(conn, again))
    assert answer.status_code == 303
    assert again != job_id
    assert (second.op, second.scope, second.tree) == (
        first.op,
        first.scope,
        first.tree,
    )
    assert second.started_by == "writer"


def test_a_writer_cannot_retry_an_admin_only_stage(
    repo: Path, panel: Panel
) -> None:
    database = Database.at(repo / "hrono.db")
    job_id = enqueue(database, "monitor", {}, tree="default")
    with database.write() as conn:
        job_store.set_status(
            conn, job_id, "failed", "x", "t", code="bad-request"
        )
    database.close()
    panel.as_("writer")

    answer = panel.client.post(
        f"/ui/jobs/{job_id}/retry?tree=default", follow_redirects=False
    )

    assert answer.status_code == 403


def test_the_runs_list_filters_and_pages(repo: Path, panel: Panel) -> None:
    database = Database.at(repo / "hrono.db")
    for n in range(30):
        job_id = enqueue(
            database, "noop" if n % 3 else "monitor", {}, tree="default"
        )
        with database.write() as conn:
            job_store.set_status(
                conn, job_id, "failed" if n % 2 else "succeeded", None, "t"
            )
    database.close()
    panel.as_("admin")

    first = panel.client.get("/ui/jobs?tree=default").text
    second = panel.client.get("/ui/jobs?tree=default&page=2").text
    failed = panel.client.get("/ui/jobs?tree=default&status=failed").text
    monitors = panel.client.get("/ui/jobs?tree=default&op=monitor").text

    assert first.count('data-job="') == 25
    assert second.count('data-job="') == 5
    assert "page 1 of 2" in first
    rows = failed.split("<tbody>")[1].split("</tbody>")[0]
    assert rows.count('data-state="failed"') == 15
    assert 'data-state="succeeded"' not in failed.split("<tbody>")[1]
    assert monitors.count("<code>monitor</code>") == 10
