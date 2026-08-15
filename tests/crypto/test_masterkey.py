from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from hrono.crypto.keys import fingerprint
from hrono.crypto.masterkey import (
    InvalidKey,
    KeyFileUnreadable,
    KeyNotProvided,
    WrongMasterKey,
    load_key,
    reconcile,
)
from hrono.db.database import open_database

KEY = Fernet.generate_key()
OTHER = Fernet.generate_key()


def test_load_key_reads_a_file(tmp_path: Path) -> None:
    path = tmp_path / "master.key"
    path.write_bytes(KEY)
    assert load_key(path, None) == KEY


def test_load_key_strips_trailing_whitespace(tmp_path: Path) -> None:
    path = tmp_path / "master.key"
    path.write_bytes(KEY + b"\n")
    assert load_key(path, None) == KEY


def test_load_key_reads_the_env_when_no_file() -> None:
    assert load_key(None, KEY.decode()) == KEY


def test_load_key_file_takes_precedence_over_env(tmp_path: Path) -> None:
    path = tmp_path / "master.key"
    path.write_bytes(KEY)
    assert load_key(path, OTHER.decode()) == KEY


def test_load_key_missing_source_raises() -> None:
    with pytest.raises(KeyNotProvided):
        load_key(None, None)


def test_load_key_empty_env_is_treated_as_missing() -> None:
    with pytest.raises(KeyNotProvided):
        load_key(None, "")


def test_load_key_unreadable_file_raises(tmp_path: Path) -> None:
    with pytest.raises(KeyFileUnreadable):
        load_key(tmp_path / "does-not-exist", None)


def test_load_key_invalid_bytes_raise() -> None:
    with pytest.raises(InvalidKey):
        load_key(None, "not-a-fernet-key")


def test_reconcile_first_run_records_fingerprint(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    record = reconcile(conn, KEY)
    assert record.key_id == 1
    assert record.fingerprint == fingerprint(KEY)
    stored = conn.execute("SELECT key_hash FROM keys").fetchall()
    assert [row["key_hash"] for row in stored] == [fingerprint(KEY)]
    conn.close()


def test_reconcile_never_stores_the_raw_key(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    dump = " ".join(
        str(tuple(row)) for row in conn.execute("SELECT * FROM keys")
    )
    assert KEY.decode() not in dump
    conn.close()


def test_reconcile_matching_restart_reuses_the_record(tmp_path: Path) -> None:
    db = tmp_path / "hrono.db"
    first = reconcile(open_database(db), KEY)
    conn = open_database(db)
    second = reconcile(conn, KEY)
    assert second.key_id == first.key_id
    assert conn.execute("SELECT count(*) FROM keys").fetchone()[0] == 1
    conn.close()


def test_reconcile_mismatch_refuses_and_mutates_nothing(tmp_path: Path) -> None:
    db = tmp_path / "hrono.db"
    reconcile(open_database(db), KEY)
    conn = open_database(db)
    before = [
        tuple(r) for r in conn.execute("SELECT key_id, key_hash FROM keys")
    ]
    with pytest.raises(WrongMasterKey):
        reconcile(conn, OTHER)
    after = [
        tuple(r) for r in conn.execute("SELECT key_id, key_hash FROM keys")
    ]
    assert before == after
    conn.close()
