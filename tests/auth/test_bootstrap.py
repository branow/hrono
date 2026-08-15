from pathlib import Path

from hrono.auth.bootstrap import BOOTSTRAP_ADMIN, bootstrap_admin
from hrono.auth.users import authenticate, create_user, list_users
from hrono.db.database import open_database


def test_bootstrap_mints_one_admin_and_returns_a_token(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    token = bootstrap_admin(conn)
    assert token
    users = list_users(conn)
    assert len(users) == 1
    assert users[0].name == BOOTSTRAP_ADMIN
    assert users[0].role == "admin"
    conn.close()


def test_bootstrapped_token_authenticates_the_admin(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    token = bootstrap_admin(conn)
    assert token is not None
    user = authenticate(conn, token)
    assert user is not None
    assert user.name == BOOTSTRAP_ADMIN
    assert user.role == "admin"
    conn.close()


def test_bootstrap_is_silent_when_a_user_already_exists(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    create_user(conn, "someone", "reader")
    assert bootstrap_admin(conn) is None
    assert [u.name for u in list_users(conn)] == ["someone"]
    conn.close()


def test_bootstrap_is_idempotent_across_calls(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    first = bootstrap_admin(conn)
    second = bootstrap_admin(conn)
    assert first is not None
    assert second is None
    assert len(list_users(conn)) == 1
    conn.close()


def test_bootstrap_never_persists_the_raw_token(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    token = bootstrap_admin(conn)
    assert token is not None
    dump = " ".join(
        str(tuple(row)) for row in conn.execute("SELECT * FROM users")
    )
    assert token not in dump
    conn.close()
