import dataclasses
import sqlite3
from pathlib import Path

import pytest

from hrono.auth.users import (
    InvalidRole,
    User,
    authenticate,
    create_user,
    delete_user,
    get_user,
    list_users,
    reset_token,
)
from hrono.crypto.tokens import hash_token
from hrono.db.database import open_database


def db(tmp_path: Path) -> sqlite3.Connection:
    return open_database(tmp_path / "hrono.db")


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return db(tmp_path)


def test_users_migration_creates_table_shape(tmp_path: Path) -> None:
    conn = db(tmp_path)
    columns = {
        row["name"]: row for row in conn.execute("PRAGMA table_info(users)")
    }
    assert set(columns) == {
        "name",
        "role",
        "token_hash",
        "created_at",
        "modified_at",
    }
    assert columns["name"]["pk"] == 1
    assert columns["role"]["notnull"] == 1
    assert columns["token_hash"]["notnull"] == 1
    conn.close()


def test_role_check_constraint_rejects_unknown_role(tmp_path: Path) -> None:
    conn = db(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO users (name, role, token_hash, created_at) "
            "VALUES ('x', 'superuser', 'h', 't')"
        )
    conn.close()


def test_token_hash_is_unique(tmp_path: Path) -> None:
    conn = db(tmp_path)
    conn.execute(
        "INSERT INTO users (name, role, token_hash, created_at) "
        "VALUES ('a', 'reader', 'shared', 't')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO users (name, role, token_hash, created_at) "
            "VALUES ('b', 'reader', 'shared', 't')"
        )
    conn.close()


def test_create_user_returns_token_once_and_stores_only_hash(
    tmp_path: Path,
) -> None:
    conn = db(tmp_path)
    user, token = create_user(conn, "alice", "admin")
    assert user == User("alice", "admin", user.created_at, user.created_at)
    assert token
    stored = conn.execute(
        "SELECT token_hash FROM users WHERE name = 'alice'"
    ).fetchone()["token_hash"]
    assert stored == hash_token(token)
    assert stored != token
    conn.close()


def test_user_read_never_exposes_token_or_hash(tmp_path: Path) -> None:
    conn = db(tmp_path)
    user, token = create_user(conn, "bob", "reader")
    assert not hasattr(user, "token")
    assert not hasattr(user, "token_hash")
    fetched = get_user(conn, "bob")
    assert fetched == user
    assert token not in str(fetched)
    conn.close()


def test_get_user_missing_returns_none(tmp_path: Path) -> None:
    conn = db(tmp_path)
    assert get_user(conn, "nobody") is None
    conn.close()


def test_list_users_returns_a_sorted_tuple(tmp_path: Path) -> None:
    conn = db(tmp_path)
    create_user(conn, "carol", "reader")
    create_user(conn, "alice", "admin")
    users = list_users(conn)
    assert isinstance(users, tuple)
    assert [user.name for user in users] == ["alice", "carol"]
    conn.close()


def test_delete_user_reports_whether_a_row_was_removed(tmp_path: Path) -> None:
    conn = db(tmp_path)
    create_user(conn, "dave", "writer")
    assert delete_user(conn, "dave") is True
    assert delete_user(conn, "dave") is False
    assert get_user(conn, "dave") is None
    conn.close()


def test_authenticate_returns_user_on_hit_and_none_on_miss(
    tmp_path: Path,
) -> None:
    conn = db(tmp_path)
    user, token = create_user(conn, "erin", "admin")
    assert authenticate(conn, token) == user
    assert authenticate(conn, "not-a-real-token") is None
    assert authenticate(conn, "") is None
    conn.close()


def test_create_user_rejects_invalid_role_before_writing(
    tmp_path: Path,
) -> None:
    conn = db(tmp_path)
    with pytest.raises(InvalidRole):
        create_user(conn, "mallory", "superuser")
    assert list_users(conn) == ()
    conn.close()


def test_user_is_frozen() -> None:
    user = User("x", "reader", "2026-08-15", "2026-08-15")
    with pytest.raises(dataclasses.FrozenInstanceError):
        user.role = "admin"  # type: ignore[misc]


def test_a_fresh_user_was_last_modified_when_it_was_created(
    conn: sqlite3.Connection,
) -> None:
    user, _ = create_user(conn, "alice", "admin")

    assert user.modified_at == user.created_at


def test_a_token_rotation_moves_modified_at_and_leaves_created_at(
    conn: sqlite3.Connection,
) -> None:
    """The audit this column exists for: when was this credential last rotated.

    Before #042 a rotation changed only the hash, so a token issued two years
    ago and never touched looked exactly like one rotated this morning.
    """
    made, _ = create_user(conn, "alice", "admin")

    rotated, _ = reset_token(conn, "alice")

    assert rotated.created_at == made.created_at
    assert rotated.modified_at > made.modified_at
    assert get_user(conn, "alice") == rotated


def test_the_rotation_returns_the_new_stamp_not_the_old_one(
    conn: sqlite3.Connection,
) -> None:
    # a caller that printed what it was handed would report the moment BEFORE
    # the rotation it had just performed
    made, _ = create_user(conn, "alice", "admin")

    rotated, _ = reset_token(conn, "alice")

    assert rotated.modified_at != made.modified_at


def test_every_read_path_carries_the_stamp(
    conn: sqlite3.Connection,
) -> None:
    _, token = create_user(conn, "alice", "admin")
    reset_token(conn, "alice")
    _, fresh = reset_token(conn, "alice")
    stamped = get_user(conn, "alice")
    assert stamped is not None

    assert list_users(conn) == (stamped,)
    assert authenticate(conn, fresh) == stamped
    assert authenticate(conn, token) is None


def test_the_last_admin_cannot_be_deleted_or_demoted(
    conn: sqlite3.Connection,
) -> None:
    from hrono.auth.users import LastAdmin, set_role

    create_user(conn, "root", "admin")
    with pytest.raises(LastAdmin):
        delete_user(conn, "root")
    with pytest.raises(LastAdmin):
        set_role(conn, "root", "reader")
    assert get_user(conn, "root").role == "admin"  # type: ignore[union-attr]
    create_user(conn, "second", "admin")
    assert set_role(conn, "root", "reader").role == "reader"
    with pytest.raises(LastAdmin):
        delete_user(conn, "second")


def test_set_role_validates_and_moves_modified_at(
    conn: sqlite3.Connection,
) -> None:
    from hrono.auth.users import set_role
    from hrono.errors import NotFound

    created, token = create_user(conn, "dave", "reader")
    with pytest.raises(InvalidRole):
        set_role(conn, "dave", "root")
    with pytest.raises(NotFound):
        set_role(conn, "nobody", "reader")
    changed = set_role(conn, "dave", "writer")
    assert changed.modified_at > created.modified_at
    assert authenticate(conn, token).role == "writer"  # type: ignore[union-attr]
