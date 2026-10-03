"""#209 (E012): the Access page — manage users from the panel.

Every test posts the forms the page draws, with the browser's own cookie. The
last-admin tests post FORGED requests (no button on the page makes them) because
the server, not the page, is what must refuse.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import authenticate, create_user, get_user, list_users
from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.registry import store as registry_store
from hrono.server.app import create_app

KEY = Fernet.generate_key()


class Panel:
    def __init__(self, client: TestClient, tokens: dict, conn: object) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn

    def sign_in(self, token: str) -> None:
        self.client.cookies.clear()
        self.client.post("/ui/login", data={"token": token})

    def as_role(self, role: str) -> None:
        self.sign_in(self.tokens[role])

    def post(self, path: str, **form: str):  # type: ignore[no-untyped-def]
        return self.client.post(path, data=form, follow_redirects=False)

    def issued(self, response) -> str:  # type: ignore[no-untyped-def]
        found = re.search(
            r'id="issued-token"[^>]*value="([^"]+)"', response.text
        )
        assert found, response.text
        return found.group(1)


@pytest.fixture
def panel(tmp_path: Path) -> Iterator[Panel]:
    conn = open_database(tmp_path / "hrono.db")
    record = reconcile(conn, KEY)
    sealed = Cipher.from_key(KEY, record.key_id).encrypt("s3cret-value")
    registry_store.insert(
        conn,
        "sources",
        "gh",
        json.dumps(
            {
                "name": "gh",
                "type": "git",
                "url": "https://example.test/r.git",
                "auth": {"method": "token", "token": sealed.ciphertext},
            }
        ),
        sealed.key_id,
        "t",
    )
    tokens = {
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
    }
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        found = Panel(client, tokens, conn)
        found.as_role("admin")
        yield found
    conn.close()


def test_the_page_lists_everyone_and_the_tab_is_drawn_for_an_admin(
    panel: Panel,
) -> None:
    page = panel.client.get("/ui/access").text
    for name in ("reader", "writer", "admin"):
        assert f"<strong>{name}</strong>" in page
    assert 'href="/ui/access?tree=default"' in page


@pytest.mark.parametrize("role", ["reader", "writer"])
def test_below_admin_cannot_see_the_page_the_tab_or_any_route(
    panel: Panel, role: str
) -> None:
    panel.as_role(role)
    assert "/ui/access" not in panel.client.get("/ui").text
    assert panel.client.get("/ui/access").status_code == 403
    for path, form in (
        ("/ui/access/create", {"name": "mallory", "role": "admin"}),
        ("/ui/access/reader/role", {"role": "admin"}),
        ("/ui/access/admin/reissue", {"confirm": "1"}),
        ("/ui/access/admin/delete", {"confirm": "1"}),
        ("/ui/access/rotate-key", {"confirm": "1"}),
    ):
        assert panel.post(path, **form).status_code == 403, path
    assert get_user(panel.conn, "mallory") is None
    assert get_user(panel.conn, "admin") is not None
    assert get_user(panel.conn, "reader").role == "reader"  # type: ignore[union-attr]


def test_a_created_reader_signs_in_and_can_only_read(panel: Panel) -> None:
    made = panel.post("/ui/access/create", name="carol", role="reader")
    assert made.status_code == 200
    token = panel.issued(made)
    assert authenticate(panel.conn, token).name == "carol"  # type: ignore[union-attr]
    panel.sign_in(token)
    assert panel.client.get("/ui").status_code == 200
    assert panel.client.get("/ui/access").status_code == 403
    assert (
        panel.post("/ui/access/create", name="x", role="reader").status_code
        == 403
    )
    assert panel.post("/ui/sync").status_code in (403, 404, 405)
    assert panel.client.post("/trees/default/sync").status_code == 403


def test_a_token_is_shown_once_and_reaches_no_url_or_reload(
    panel: Panel,
) -> None:
    made = panel.post("/ui/access/create", name="carol", role="reader")
    token = panel.issued(made)
    assert made.headers["cache-control"] == "no-store"
    assert "location" not in made.headers
    for url in ("/ui/access", "/ui/access?tree=default"):
        assert token not in panel.client.get(url).text
    assert token not in panel.client.get("/users").text
    only_hash = panel.conn.execute(  # type: ignore[attr-defined]
        "SELECT token_hash FROM users WHERE name = 'carol'"
    ).fetchone()[0]
    assert token != only_hash


def test_reissue_needs_confirmation_then_swaps_the_token(panel: Panel) -> None:
    old = panel.tokens["reader"]
    refused = panel.post("/ui/access/reader/reissue")
    assert refused.status_code == 422
    assert authenticate(panel.conn, old) is not None
    done = panel.post("/ui/access/reader/reissue", confirm="1")
    new = panel.issued(done)
    assert authenticate(panel.conn, old) is None
    assert authenticate(panel.conn, new).name == "reader"  # type: ignore[union-attr]


def test_a_role_change_is_saved_and_names_the_user(panel: Panel) -> None:
    done = panel.post("/ui/access/reader/role", role="writer", tree="default")
    assert done.status_code == 303
    assert "reader+is+now+writer" in done.headers["location"]
    assert get_user(panel.conn, "reader").role == "writer"  # type: ignore[union-attr]
    assert panel.post("/ui/access/reader/role", role="root").status_code == 422


def test_delete_needs_a_confirmation_that_names_the_user(panel: Panel) -> None:
    ask = panel.client.get("/ui/access?delete=writer").text
    assert "Delete writer" in ask
    assert panel.post("/ui/access/writer/delete").status_code == 422
    assert get_user(panel.conn, "writer") is not None
    done = panel.post("/ui/access/writer/delete", confirm="1")
    assert done.status_code == 303
    assert get_user(panel.conn, "writer") is None
    assert (
        panel.post("/ui/access/writer/delete", confirm="1").status_code == 422
    )


@pytest.mark.parametrize(
    "path,form",
    [
        ("/ui/access/admin/delete", {"confirm": "1"}),
        ("/ui/access/admin/role", {"role": "reader"}),
    ],
    ids=["delete", "demote"],
)
def test_the_last_admin_is_refused_even_by_a_forged_post(
    panel: Panel, path: str, form: dict[str, str]
) -> None:
    refused = panel.post(path, **form)
    assert refused.status_code == 409
    assert "last admin" in refused.text
    assert get_user(panel.conn, "admin").role == "admin"  # type: ignore[union-attr]


def test_with_a_second_admin_either_may_go_and_one_is_always_left(
    panel: Panel,
) -> None:
    panel.post("/ui/access/reader/role", role="admin")
    assert panel.post("/ui/access/admin/delete", confirm="1").status_code == 303
    panel.sign_in(panel.tokens["reader"])
    assert (
        panel.post("/ui/access/reader/role", role="writer").status_code == 409
    )
    assert [u.name for u in list_users(panel.conn) if u.role == "admin"] == [
        "reader"
    ]


def test_the_api_refuses_the_last_admin_too(panel: Panel) -> None:
    head = {"Authorization": f"Bearer {panel.tokens['admin']}"}
    gone = panel.client.delete("/users/admin", headers=head)
    assert gone.status_code == 409


@pytest.mark.parametrize("name", ["", "a b", "../x", "a/b", "-x"])
def test_a_name_that_would_break_a_url_is_refused(
    panel: Panel, name: str
) -> None:
    refused = panel.post("/ui/access/create", name=name, role="reader")
    assert refused.status_code == 422
    assert len(list_users(panel.conn)) == 3


def test_a_duplicate_name_is_a_conflict_with_the_name_kept(
    panel: Panel,
) -> None:
    refused = panel.post("/ui/access/create", name="reader", role="reader")
    assert refused.status_code == 409


def test_rotating_the_key_reports_what_it_did_and_checks_the_old_key(
    panel: Panel,
) -> None:
    fresh = Fernet.generate_key().decode()
    wrong = panel.post(
        "/ui/access/rotate-key",
        old_key=Fernet.generate_key().decode(),
        new_key=fresh,
        confirm="1",
    )
    assert wrong.status_code == 403
    assert fresh not in wrong.text
    unconfirmed = panel.post(
        "/ui/access/rotate-key", old_key=KEY.decode(), new_key=fresh
    )
    assert unconfirmed.status_code == 422
    done = panel.post(
        "/ui/access/rotate-key",
        old_key=KEY.decode(),
        new_key=fresh,
        confirm="1",
    )
    assert done.status_code == 200
    assert "Master key rotated" in done.text
    assert "restart" in done.text
    assert "1 secret re-encrypted" in done.text
    assert fresh not in done.text
    row = registry_store.get(panel.conn, "sources", "gh")  # type: ignore[arg-type]
    token = json.loads(row["config"])["auth"]["token"]
    assert (
        Cipher.from_key(fresh.encode(), row["key_id"]).decrypt(
            row["key_id"], token
        )
        == "s3cret-value"
    )
