import json
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from hrono.crypto.cipher import Cipher
from hrono.db.database import Database
from hrono.ingest import store
from hrono.ingest.split_op import SplitError, _instance, split_source
from hrono.ingest.sync import sync
from hrono.jobs import store as jobs_store
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.jobs.scope import fan_out
from hrono.jobs.worker import Worker
from hrono.registry import store as registry_store

KEY = Fernet.generate_key()


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Database, str]]:
    monkeypatch.chdir(tmp_path)
    url = make_repo(tmp_path / "remote", FILES)
    db = Database.at(tmp_path / "hrono.db")
    with db.connect() as conn:
        register(conn, "repo", url)
    sync(job("sync", "repo"), JobContext(db))
    yield db, _git(tmp_path / "remote", "rev-parse", "HEAD")
    db.close()


def test_split_populates_sections_passages_and_contents(
    synced: tuple[Database, str],
) -> None:
    db, commit = synced
    split_source(job("split", "repo"), JobContext(db))
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
) -> None:
    db, _ = synced
    split_source(job("split", "repo"), JobContext(db))
    with db.connect() as conn:
        for section in store.list_sections(conn, "repo"):
            passages = store.list_passages(conn, section["id"])
            rebuilt = b"".join(
                store.get_content(conn, p["content_hash"]) for p in passages
            )
            assert rebuilt == store.get_content(conn, section["content_hash"])


def test_data_file_uses_the_smaller_section_budget(
    synced: tuple[Database, str],
) -> None:
    db, _ = synced
    split_source(job("split", "repo"), JobContext(db))
    with db.connect() as conn:
        json_sections = [
            s
            for s in store.list_sections(conn, "repo")
            if s["path"] == "data.json"
        ]
    # the 2 KB data budget forces more than one section on the big JSON file
    assert len(json_sections) > 1


def test_resplit_is_idempotent(synced: tuple[Database, str]) -> None:
    db, _ = synced
    split_source(job("split", "repo"), JobContext(db))
    with db.connect() as conn:
        before = (
            len(store.list_sections(conn, "repo")),
            store.content_count(conn),
            conn.execute("SELECT COUNT(*) FROM passages").fetchone()[0],
        )
    split_source(job("split", "repo"), JobContext(db))
    with db.connect() as conn:
        after = (
            len(store.list_sections(conn, "repo")),
            store.content_count(conn),
            conn.execute("SELECT COUNT(*) FROM passages").fetchone()[0],
        )
    assert before == after


def test_identical_bodies_across_files_dedup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    same = "shared identical body line one\nand line two here as well now.\n"
    url = make_repo(tmp_path / "remote", {"a.txt": same, "b.txt": same})
    db = Database.at(tmp_path / "hrono.db")
    with db.connect() as conn:
        register(conn, "repo", url)
    sync(job("sync", "repo"), JobContext(db))
    split_source(job("split", "repo"), JobContext(db))
    with db.connect() as conn:
        sections = store.list_sections(conn, "repo")
        # two files, same bytes -> two sections sharing one content row
        assert len(sections) == 2
        assert len({s["content_hash"] for s in sections}) == 1
    db.close()


def test_split_before_sync_raises_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    db = Database.at(tmp_path / "hrono.db")
    with db.connect() as conn:
        register(conn, "repo", "file:///nope")
    with pytest.raises(SplitError):
        split_source(job("split", "repo"), JobContext(db))
    db.close()


def test_split_runs_as_a_registered_job_op(
    synced: tuple[Database, str],
) -> None:
    db, _ = synced
    worker = Worker(db, cipher=Cipher.from_key(KEY, 1))
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
    assert _instance("https://github.com/acme/webphone") == (
        "github.com/acme/webphone"
    )
    assert _instance("git@github.com:acme/webphone.git") == (
        "github.com/acme/webphone"
    )
    assert _instance("ssh://git@gitlab.com/x/y") == "gitlab.com/x/y"
