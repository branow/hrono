import json
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from hrono.crypto.cipher import Cipher
from hrono.db.database import Database
from hrono.ingest import diff, store
from hrono.ingest.readers import READERS, git_instance
from hrono.ingest.split_op import SplitError, split_source
from hrono.ingest.sync import sync
from hrono.jobs import store as jobs_store
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.jobs.scope import fan_out
from hrono.jobs.worker import Worker
from hrono.paths import cache_root
from hrono.registry import store as registry_store
from tests.context import job_context
from tests.repo_template import memoized

KEY = Fernet.generate_key()


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@memoized
def make_repo(path: Path, files: dict[str, str]) -> str:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "Test")
    for name, content in files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "first")
    return path.as_uri()


def register(conn: object, name: str, url: str) -> None:
    body = {"name": name, "type": "git", "url": url, "auth": {"method": "none"}}
    registry_store.insert(conn, "sources", name, json.dumps(body), None, "t")


def job(op: str, name: str) -> Job:
    return Job(
        id="j",
        parent_id=None,
        tree=None,
        op=op,
        scope={"type": "source", "name": name},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


FILES = {
    "svc.py": (
        "class Contact:\n"
        + "".join(
            f"    def m{i}(self):\n        return {i}\n" for i in range(30)
        )
        + "\ndef top():\n    pass\n"
    ),
    "README.md": "# Title\n\n"
    + ("some documentation prose here. " * 60)
    + "\n",
    "data.json": "[\n"
    + ",\n".join(f'  {{"i": {i}}}' for i in range(200))
    + "\n]\n",
}


@pytest.fixture
def synced(
    tmp_path: Path,
) -> Iterator[tuple[Database, str]]:
    url = make_repo(tmp_path / "remote", FILES)
    db = Database.at(tmp_path / "hrono.db")
    with db.connect() as conn:
        register(conn, "repo", url)
    sync(job("sync", "repo"), job_context(db, tmp_path))
    yield db, _git(tmp_path / "remote", "rev-parse", "HEAD")
    db.close()


def test_split_populates_sections_passages_and_contents(
    synced: tuple[Database, str],
    tmp_path: Path,
) -> None:
    db, commit = synced
    split_source(job("split", "repo"), job_context(db, tmp_path))
    with db.connect() as conn:
        sections = store.list_sections(conn, "repo")
        assert sections
        paths = {s["path"] for s in sections}
        assert paths == {"svc.py", "README.md", "data.json"}
        for section in sections:
            assert section["source_type"] == "git"
            assert section["version"] == commit
            assert section["uri"].startswith("git://")
            assert section["uri"].endswith(f"@{commit}")
            passages = store.list_passages(conn, section["id"])
            assert passages
            for passage in passages:
                assert json.loads(passage["sp_paths"])  # at least one sp path


def test_reassembly_from_storage_over_code_docs_data(
    synced: tuple[Database, str],
    tmp_path: Path,
) -> None:
    db, _ = synced
    split_source(job("split", "repo"), job_context(db, tmp_path))
    with db.connect() as conn:
        for section in store.list_sections(conn, "repo"):
            passages = store.list_passages(conn, section["id"])
            rebuilt = b"".join(
                store.get_content(conn, p["content_hash"]) for p in passages
            )
            assert rebuilt == store.get_content(conn, section["content_hash"])


def test_data_file_uses_the_smaller_section_budget(
    synced: tuple[Database, str],
    tmp_path: Path,
) -> None:
    db, _ = synced
    split_source(job("split", "repo"), job_context(db, tmp_path))
    with db.connect() as conn:
        json_sections = [
            s
            for s in store.list_sections(conn, "repo")
            if s["path"] == "data.json"
        ]
    # the 2 KB data budget forces more than one section on the big JSON file
    assert len(json_sections) > 1


def test_resplit_is_idempotent(
    synced: tuple[Database, str], tmp_path: Path
) -> None:
    db, _ = synced
    split_source(job("split", "repo"), job_context(db, tmp_path))
    with db.connect() as conn:
        before = (
            len(store.list_sections(conn, "repo")),
            store.content_count(conn),
            conn.execute("SELECT COUNT(*) FROM passages").fetchone()[0],
        )
    split_source(job("split", "repo"), job_context(db, tmp_path))
    with db.connect() as conn:
        after = (
            len(store.list_sections(conn, "repo")),
            store.content_count(conn),
            conn.execute("SELECT COUNT(*) FROM passages").fetchone()[0],
        )
    assert before == after


def test_identical_bodies_across_files_dedup(
    tmp_path: Path,
) -> None:
    same = "shared identical body line one\nand line two here as well now.\n"
    url = make_repo(tmp_path / "remote", {"a.txt": same, "b.txt": same})
    db = Database.at(tmp_path / "hrono.db")
    with db.connect() as conn:
        register(conn, "repo", url)
    sync(job("sync", "repo"), job_context(db, tmp_path))
    split_source(job("split", "repo"), job_context(db, tmp_path))
    with db.connect() as conn:
        sections = store.list_sections(conn, "repo")
        # two files, same bytes -> two sections sharing one content row
        assert len(sections) == 2
        assert len({s["content_hash"] for s in sections}) == 1
    db.close()


def test_split_before_sync_raises_cleanly(
    tmp_path: Path,
) -> None:
    db = Database.at(tmp_path / "hrono.db")
    with db.connect() as conn:
        register(conn, "repo", "file:///nope")
    with pytest.raises(SplitError):
        split_source(job("split", "repo"), job_context(db, tmp_path))
    db.close()


def test_split_runs_as_a_registered_job_op(
    synced: tuple[Database, str],
    tmp_path: Path,
) -> None:
    db, _ = synced
    worker = Worker(
        db,
        cipher=Cipher.from_key(KEY, 1),
        cache_root=cache_root(tmp_path / "hrono.db"),
    )
    worker.start()
    try:
        parent = fan_out(db, "split", {"type": "all"})
        deadline = time.monotonic() + 5.0
        leaves: list = []
        while time.monotonic() < deadline:
            with db.connect() as conn:
                leaves = [
                    r
                    for r in jobs_store.list_jobs(conn)
                    if r["parent_id"] == parent
                ]
            if leaves and all(
                r["status"] in ("succeeded", "failed") for r in leaves
            ):
                break
            time.sleep(0.01)
    finally:
        worker.stop()
        worker.join(timeout=5)
    assert [r["status"] for r in leaves] == ["succeeded"]
    with db.connect() as conn:
        assert store.list_sections(conn, "repo")


def test_instance_normalises_url_forms() -> None:
    assert git_instance(
        {"url": "https://github.com/acme/webphone"}, Path(".")
    ) == ("github.com/acme/webphone")
    assert git_instance(
        {"url": "git@github.com:acme/webphone.git"}, Path(".")
    ) == ("github.com/acme/webphone")
    assert (
        git_instance({"url": "ssh://git@gitlab.com/x/y"}, Path("."))
        == "gitlab.com/x/y"
    )


def test_two_working_directories_share_one_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the cache hangs off the database, so the working directory cannot move
    # it: a server in one directory and an op driver in another must not grow
    # TWO clone sets for ONE database, because diffing against the stale one
    # invents changes (including a reversed rename).
    url = make_repo(tmp_path / "remote", {"a.txt": "alpha body here\n"})
    db_path = tmp_path / "data" / "hrono.db"
    db_path.parent.mkdir()
    db = Database.at(db_path)
    with db.connect() as conn:
        register(conn, "repo", url)

    here = tmp_path / "here"
    there = tmp_path / "there"
    here.mkdir()
    there.mkdir()
    context = JobContext(db, None, cache_root(db_path))

    monkeypatch.chdir(here)
    sync(job("sync", "repo"), context)
    monkeypatch.chdir(there)
    split_source(job("split", "repo"), context)

    clones = sorted(
        p for p in tmp_path.rglob("cache/sources/repo") if p.is_dir()
    )
    assert clones == [tmp_path / "data" / "cache" / "sources" / "repo"]
    assert not (here / ".hrono").exists()
    assert not (there / ".hrono").exists()
    with db.connect() as conn:
        assert len(store.list_sections(conn, "repo")) == 1
    db.close()


def test_a_second_process_directory_sees_no_phantom_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the measurement hazard of a second clone set: re-diffing the same corpus
    # from a different directory must report nothing, not a tree of invented
    # changes.
    url = make_repo(tmp_path / "remote", {"a.txt": "alpha body here\n"})
    db_path = tmp_path / "data" / "hrono.db"
    db_path.parent.mkdir()
    db = Database.at(db_path)
    with db.connect() as conn:
        register(conn, "repo", url)
    context = JobContext(db, None, cache_root(db_path))
    monkeypatch.chdir(tmp_path)
    sync(job("sync", "repo"), context)
    split_source(job("split", "repo"), context)

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    sync(job("sync", "repo"), context)
    with db.connect() as conn:
        changes = diff.diff(
            conn,
            "repo",
            READERS["git"],
            {"url": "https://example.com/repo.git"},
            context.cache_for("repo"),
        )
    assert changes == ()
    db.close()
