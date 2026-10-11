"""A run says what it did, what failed and where, and can be retried."""

import json
import sqlite3
import subprocess
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
from hrono.registry import store as registry_store
from hrono.server.app import create_app
from hrono.server.failures import SAID
from hrono.summarize import store as condensations
from hrono.tree.maintain import maintain
from hrono.tree.sync_chain import sync
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


def _run(
    tmp_path: Path, op: str = "maintain", **seams: object
) -> tuple[Database, str]:
    """A run through the REAL worker: its own result and failure paths."""
    database = Database.at(tmp_path / "hrono.db")
    job_id = enqueue(database, op, {}, tree="default", started_by="ana")
    made = {"maintain": maintain, "sync-tree": sync}[op]
    worker = Worker(
        database,
        ops={op: partial(made, encoder_for=fake_encoder, **seams)},
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
    def __init__(
        self,
        client: TestClient,
        tokens: dict[str, str],
        conn: sqlite3.Connection,
    ) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn

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
        yield Panel(client, tokens, conn)
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
        "restore-pins",
        "brief",
        "build-tree",
        "embed",
        "health",
    ]
    assert all(s["seconds"] >= 0 for s in stages)
    assert stages[3]["result"]["condensed"] == 9
    assert job.result["tree"]["topics_added"] > 0  # type: ignore[index]


def test_a_first_build_reports_what_sync_split_and_embed_did(
    repo: Path, panel: Panel
) -> None:
    database, job_id = _run(repo, client=Writing(), build=fake_build)
    panel.as_("writer")
    page = panel.client.get(f"/ui/jobs/{job_id}?tree=default").text

    with database.connect() as conn:
        job = to_job(job_store.get(conn, job_id))
    sync, split, embed = job.result["stages"][:3]  # type: ignore[index]

    assert sync["result"] == {"fetched": 1}
    assert split["result"]["files_changed"] == 9
    assert split["result"]["sections_cut"] >= 9
    assert split["result"]["files_gone"] == 0
    assert embed["result"]["embedded"] > split["result"]["sections_cut"]
    assert "1 new version fetched" in page
    assert "9 new or changed files read" in page
    assert "pieces of text embedded" in page


def test_an_unchanged_rerun_reads_nothing_to_do(
    repo: Path, panel: Panel
) -> None:
    _run(repo, client=Writing(), build=fake_build)
    database, job_id = _run(repo, client=Writing(), build=fake_build)
    panel.as_("writer")

    with database.connect() as conn:
        job = to_job(job_store.get(conn, job_id))
    page = panel.client.get(f"/ui/jobs/{job_id}?tree=default").text
    sync, split, embed = job.result["stages"][:3]  # type: ignore[index]

    assert sync["result"] == {"fetched": 0}
    assert split["result"] == {
        "files_changed": 0,
        "sections_cut": 0,
        "files_gone": 0,
    }
    assert embed["result"] == {"embedded": 0}
    timeline = page.split('id="stages"')[1].split("</section>")[0]
    assert timeline.count("nothing to do") >= 3
    assert "files read" not in timeline and "embedded" not in timeline


TALKED_BACK = "Could you paste the file you would like me to condense?"


class Refusing(Writing):
    """Talks back for one file's section, writes every other summary."""

    def __init__(self, about: str) -> None:
        super().__init__()
        self.about = about

    def complete(self, request: CompletionRequest) -> CompletionResult:
        if self.about in request.content:
            return CompletionResult(TALKED_BACK, Usage(4, 4))
        return super().complete(request)


def _store_talk_back(database: Database, *paths: str) -> None:
    """Cache a talked-back condensation for these sections."""
    with database.write() as conn:
        for path in paths:
            digest = conn.execute(
                "SELECT content_hash FROM sections WHERE path = ?", (path,)
            ).fetchone()[0]
            conn.execute(
                "DELETE FROM condensations WHERE content_hash = ?", (digest,)
            )
            condensations.upsert(conn, digest, "sonnet", TALKED_BACK, 1, 1)
        registry_store.insert(  # the sync's propagate stage asks a judge
            conn,
            "prompts",
            "judge",
            json.dumps(
                {"name": "judge", "role": "judge", "template": "{source}"}
            ),
            None,
            "t",
        )


def _update_stage(database: Database, job_id: str) -> dict[str, object]:
    with database.connect() as conn:
        job = to_job(job_store.get(conn, job_id))
    assert job.status == "succeeded"
    stages = job.result["stages"]  # type: ignore[index]
    return next(s for s in stages if s["op"] == "update")["result"]


def test_an_unchanged_sync_shows_what_its_condense_step_did(
    repo: Path, panel: Panel
) -> None:
    # the update stage must not say only `changed: false` while it spends
    # model calls redoing talked-back condensations; the spend is shown
    database, _ = _run(repo, client=Writing(), build=fake_build)
    _store_talk_back(database, "f4.txt", "f5.txt")
    database.close()

    database, job_id = _run(
        repo, "sync-tree", client=Refusing("module 5"), core_labeler=None
    )
    panel.as_("writer")
    page = panel.client.get(f"/ui/jobs/{job_id}?tree=default").text
    stage = _update_stage(database, job_id)
    database.close()
    timeline = page.split('id="stages"')[1].split("</section>")[0]

    assert stage["changed"] is False
    assert stage["condense"] == {
        "condensed": 1,
        "refused": 1,
        "tokens": {"input": 12, "output": 12},
    }
    assert "1 section condensed" in timeline
    assert "1 reply that was not a summary, not kept" in timeline


def test_a_sync_after_a_refusal_runs_no_condense_step(repo: Path) -> None:
    database, _ = _run(repo, client=Writing(), build=fake_build)
    _store_talk_back(database, "f4.txt")
    database.close()
    _run(repo, "sync-tree", client=Refusing("module 4"), core_labeler=None)

    database, job_id = _run(
        repo, "sync-tree", client=Refusing("module 4"), core_labeler=None
    )
    stage = _update_stage(database, job_id)
    database.close()

    assert stage == {"changed": False, "batch": None}


def test_a_rerun_after_an_edit_reports_only_the_edit(repo: Path) -> None:
    _run(repo, client=Writing(), build=fake_build)
    source = repo / "src-repo"
    (source / "f1.txt").write_text("module 1 now does something else\n")
    (source / "f2.txt").unlink()
    subprocess.run(["git", "-C", str(source), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(source), "commit", "-qm", "edit"], check=True
    )

    database, job_id = _run(repo, client=Writing(), build=fake_build)

    with database.connect() as conn:
        job = to_job(job_store.get(conn, job_id))
    sync, split = job.result["stages"][:2]  # type: ignore[index]
    assert sync["result"] == {"fetched": 1}
    assert split["result"] == {
        "files_changed": 1,
        "sections_cut": 1,
        "files_gone": 1,
    }


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
    item = str(job.error_details["item"])  # type: ignore[index]
    assert item.startswith("sections ")  # a pack fails as one call
    assert "f4.txt" in item.split(", ")


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
    timeline = page.split('id="stages"')[1].split("</section>")[0]
    rows = timeline.count("<li>")
    assert f"{rows - 1} of {rows} done" in timeline  # the header agrees
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


def test_the_runs_list_reads_one_page_of_a_long_history(
    repo: Path, panel: Panel
) -> None:
    for n in range(5000):
        stamp = f"2026-10-03T{n:05d}"
        job_store.insert(
            panel.conn, f"job_{n:05d}", None, "default", "sync", "{}", stamp
        )
        job_store.set_status(
            panel.conn, f"job_{n:05d}", "succeeded", None, stamp
        )
    panel.as_("admin")
    statements: list[str] = []
    panel.conn.set_trace_callback(statements.append)

    started = time.monotonic()
    page = panel.client.get("/ui/jobs?tree=default").text
    took = time.monotonic() - started
    panel.conn.set_trace_callback(None)

    assert page.count('data-job="') == 25
    assert 'data-job="job_04999"' in page  # newest first
    assert "page 1 of 200" in page
    assert len(statements) < 100, f"{len(statements)} statements"
    assert took < 2, f"{took:.2f}s"
