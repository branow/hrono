from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import BaseModel

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.registry.descriptor import Descriptor, ValidationFailed
from hrono.registry.engine import build_router
from hrono.server.app import create_app

KEY = Fernet.generate_key()


class Widget(BaseModel):
    name: str
    value: int


def _reject_negative(config: dict[str, object]) -> None:
    if int(config["value"]) < 0:  # type: ignore[call-overload]
        raise ValidationFailed("value must be non-negative")


WIDGETS = Descriptor(
    collection="widgets",
    model=Widget,
    secret_paths=(),
    write_role="writer",
    validate=_reject_negative,
)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[tuple[TestClient, dict[str, str]]]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    admin = {
        "Authorization": f"Bearer {create_user(conn, 'admin', 'admin')[1]}"
    }
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    app.include_router(build_router(WIDGETS))
    with TestClient(app) as opened:
        yield opened, admin
    conn.close()


def test_a_new_collection_needs_only_a_descriptor(
    client: tuple[TestClient, dict[str, str]],
) -> None:
    opened, admin = client
    created = opened.post(
        "/widgets", json={"name": "w1", "value": 5}, headers=admin
    )
    assert created.status_code == 201
    listed = opened.get("/widgets", headers=admin)
    assert [w["name"] for w in listed.json()] == ["w1"]


def test_validation_hook_rejection_is_400(
    client: tuple[TestClient, dict[str, str]],
) -> None:
    opened, admin = client
    rejected = opened.post(
        "/widgets", json={"name": "bad", "value": -1}, headers=admin
    )
    assert rejected.status_code == 400
    assert "non-negative" in rejected.json()["detail"]
