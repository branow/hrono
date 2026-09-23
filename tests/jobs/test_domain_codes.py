"""#145: a domain error records ITS code, not everyone's code.

#109 guaranteed every failure has a code. This is the half that makes the code
worth reading: a client can tell a source that would not sync from a model that
would not load, without parsing a sentence.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster import ClusterError, TooFewPoints
from hrono.crypto.cipher import DecryptError
from hrono.db.database import Database
from hrono.embed.runner import EmbedError
from hrono.errors import AppError, Conflict, DomainError, as_app_error
from hrono.ingest import SyncError
from hrono.ingest.split_op import SplitError
from hrono.jobs import store
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.jobs.worker import Worker, enqueue

KEBAB = "abcdefghijklmnopqrstuvwxyz-"


def _subclasses(base: type) -> set[type]:
    found = set(base.__subclasses__())
    for child in tuple(found):
        found |= _subclasses(child)
    return found


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    yield database
    database.close()


def _run(db: Database, error: Exception) -> sqlite3.Row:
    def op(job: Job, context: JobContext) -> None:
        raise error

    worker = Worker(db, {"boom": op})  # type: ignore[dict-item]
    worker.start()
    try:
        job_id = enqueue(db, "boom", {})
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            with db.connect() as conn:
                row = store.get(conn, job_id)
            if row is not None and row["status"] in ("succeeded", "failed"):
                return row
            time.sleep(0.01)
        raise AssertionError("the job never finished")
    finally:
        worker.stop()
        worker.join(timeout=5)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (SyncError("the remote refused"), "sync-error"),
        (SplitError("that source is not synced"), "split-error"),
        (EmbedError("no embedding model available"), "embed-error"),
        (ClusterError("the backend is not installed"), "cluster-error"),
        (TooFewPoints("11 < 12"), "too-few-points"),
        (DecryptError("the token is malformed"), "decrypt-error"),
    ],
)
def test_a_job_records_the_failures_own_code(
    db: Database, error: Exception, code: str
) -> None:
    row = _run(db, error)

    assert row["status"] == "failed"
    assert row["error_code"] == code
    assert row["error"] == str(error)  # its own wording, unchanged
    assert json.loads(row["error_details"]) == {"type": type(error).__name__}


def test_a_foreign_exception_is_still_opaque(db: Database) -> None:
    # the #109 rule holds: a driver's wording is not hrono's answer, and its
    # code is the generic one precisely because we cannot vouch for it.
    row = _run(db, sqlite3.IntegrityError("poisoned mid-transaction"))

    assert row["error_code"] == "internal-error"
    assert row["error"] == "the job failed"
    assert "poisoned" not in json.dumps(row["error_details"])


def test_an_app_error_keeps_its_own_code_and_status() -> None:
    error = Conflict("a reshaping job holds the tree")
    mapped = as_app_error(error)

    assert mapped is error
    assert mapped.code == "conflict"
    assert mapped.status_code == 409


def test_every_domain_error_declares_a_unique_kebab_case_code() -> None:
    # walked, not listed: a new domain error that forgets its code, or copies
    # another's, fails here rather than reaching a client as someone else's.
    import hrono.cluster  # noqa: F401
    import hrono.crypto.cipher  # noqa: F401
    import hrono.embed.runner  # noqa: F401
    import hrono.ingest  # noqa: F401
    import hrono.ingest.split_op  # noqa: F401

    codes: dict[str, str] = {}
    for kind in _subclasses(DomainError):
        code = kind.code
        assert code, f"{kind.__name__} declares no code"
        assert set(code) <= set(KEBAB), f"{kind.__name__}: {code!r}"
        if kind.__base__ is not DomainError:
            continue  # a subclass may narrow its parent's code, or share it
        assert code not in codes, f"{kind.__name__} reuses {codes[code]}'s"
        codes[code] = kind.__name__
    assert len(codes) >= 5


def test_a_domain_error_is_not_an_app_error() -> None:
    # they stay separate on purpose: a DomainError knows nothing about
    # transport, and a boundary is what gives it a status.
    assert not issubclass(DomainError, AppError)
    assert as_app_error(SyncError("x")).status_code == 500
