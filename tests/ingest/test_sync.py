import json
import subprocess
import time
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database, open_database
from hrono.ingest.sync import SyncError, sync
from hrono.jobs import store
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.jobs.scope import fan_out
from hrono.jobs.worker import Worker
from hrono.registry import store as registry_store

KEY = Fernet.generate_key()


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def make_repo(path: Path, content: str = "one") -> str:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    git(path, "config", "user.email", "t@example.com")
    git(path, "config", "user.name", "Test")
    (path / "a.txt").write_text(content)
    git(path, "add", "-A")
    git(path, "commit", "-qm", "first")
    return path.as_uri()


def register(
    conn: object, name: str, url: str, auth: dict, key_id: int | None = None
) -> None:
    body = {"name": name, "type": "git", "url": url, "auth": auth}
    registry_store.insert(conn, "sources", name, json.dumps(body), key_id, "t")


def job(name: str) -> Job:
    return Job(
        id="job_x",
        parent_id=None,
        tree=None,
        op="sync",
        scope={"type": "source", "name": name},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


def version(db: Database, name: str) -> str | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT version FROM source_state WHERE source = ?", (name,)
        ).fetchone()
    return row["version"] if row is not None else None


def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    monkeypatch.chdir(tmp_path)
    return Database(open_database(tmp_path / "hrono.db"))


def test_first_sync_clones_and_captures_the_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = make_repo(tmp_path / "remote")
    db = setup(tmp_path, monkeypatch)
    with db.connect() as conn:
        register(conn, "repo", url, {"method": "none"})
    sync(job("repo"), JobContext(db))
    assert version(db, "repo") == git(tmp_path / "remote", "rev-parse", "HEAD")
    assert (tmp_path / ".hrono/cache/sources/repo/a.txt").read_text() == "one"
    db.close()


def test_resync_unchanged_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = make_repo(tmp_path / "remote")
    db = setup(tmp_path, monkeypatch)
    with db.connect() as conn:
        register(conn, "repo", url, {"method": "none"})
    sync(job("repo"), JobContext(db))
    first = version(db, "repo")
    sync(job("repo"), JobContext(db))
    assert version(db, "repo") == first
    db.close()


def test_resync_after_remote_advances_updates_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    remote = tmp_path / "remote"
    url = make_repo(remote)
    db = setup(tmp_path, monkeypatch)
    with db.connect() as conn:
        register(conn, "repo", url, {"method": "none"})
    sync(job("repo"), JobContext(db))
    old = version(db, "repo")
    (remote / "b.txt").write_text("two")
    git(remote, "add", "-A")
    git(remote, "commit", "-qm", "second")
    sync(job("repo"), JobContext(db))
    new = version(db, "repo")
    assert new != old
    assert new == git(remote, "rev-parse", "HEAD")
    db.close()


def test_bad_source_fails_cleanly_without_a_half_written_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = setup(tmp_path, monkeypatch)
    missing = (tmp_path / "nope").as_uri()
    with db.connect() as conn:
        register(conn, "repo", missing, {"method": "none"})
    with pytest.raises(SyncError):
        sync(job("repo"), JobContext(db))
    assert not (tmp_path / ".hrono/cache/sources/repo").exists()
    db.close()


def test_token_auth_is_decrypted_and_never_leaks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = make_repo(tmp_path / "remote")
    db = setup(tmp_path, monkeypatch)
    cipher = Cipher.from_key(KEY, 1)
    with db.connect() as conn:
        reconcile(conn, KEY)
        secret = cipher.encrypt("gh-secret-token")
        register(
            conn,
            "repo",
            url,
            {"method": "token", "token": secret.ciphertext},
            key_id=1,
        )
    sync(job("repo"), JobContext(db, cipher))
    assert version(db, "repo") is not None
    with db.connect() as conn:
        dump = str(conn.execute("SELECT * FROM source_state").fetchall())
    assert "gh-secret-token" not in dump
    db.close()


def test_sync_runs_as_a_registered_job_op(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = make_repo(tmp_path / "remote")
    db = setup(tmp_path, monkeypatch)
    with db.connect() as conn:
        register(conn, "repo", url, {"method": "none"})
    worker = Worker(db, cipher=Cipher.from_key(KEY, 1))
    worker.start()
    try:
        parent = fan_out(db, "sync", {"type": "all"})
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            with db.connect() as conn:
                leaves = [
                    r for r in store.list_jobs(conn) if r["parent_id"] == parent
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
    assert version(db, "repo") is not None
    db.close()
