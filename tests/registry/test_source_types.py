"""A source is declared by its TYPE, and git is one variant.

This pins the property that makes a new reader cheap: a new source type is a
model variant plus a validator table entry, and the registry engine that
stores it does not change. The second variant is defined HERE rather than in
`sources.py` — an unused model there would be speculative structure, and it
would prove nothing this does not.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated, Literal

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, RootModel

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.registry.collections.sources import SOURCES, GitSource
from hrono.registry.descriptor import Descriptor, ValidationFailed
from hrono.registry.engine import build_router
from hrono.registry.validation.git_validation import validate_git
from hrono.registry.validation.source_validation import (
    VALIDATORS,
    validate_source,
)
from hrono.server.app import create_app

KEY = Fernet.generate_key()
SPACE = "https://example.atlassian.net/wiki/spaces/ENG"


class FakeSource(BaseModel):
    """A second reader, as a new source type adds one.

    No url, no auth, its own scope.
    """

    name: str
    type: Literal["fake"]
    space: str


class TwoTypes(
    RootModel[Annotated[GitSource | FakeSource, Field(discriminator="type")]]
):
    pass


@pytest.fixture
def client(tmp_path: Path) -> Iterator[tuple[TestClient, dict[str, str]]]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    admin = {
        "Authorization": f"Bearer {create_user(conn, 'admin', 'admin')[1]}"
    }
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as opened:
        yield opened, admin
    conn.close()


@pytest.fixture
def extended(
    client: tuple[TestClient, dict[str, str]],
) -> Iterator[tuple[TestClient, dict[str, str], list[str]]]:
    """The whole cost of adding a source type: one variant, one table entry."""
    seen: list[str] = []

    def validate_fake(
        config: dict[str, object], context: object = None
    ) -> None:
        seen.append(str(config["space"]))

    opened, admin = client
    descriptor = Descriptor(
        collection="fake-sources",
        model=TwoTypes,
        secret_paths=SOURCES.secret_paths,
        write_role=SOURCES.write_role,
        validate=validate_source,
    )
    VALIDATORS["fake"] = validate_fake  # type: ignore[assignment]
    opened.app.include_router(build_router(descriptor))
    try:
        yield opened, admin, seen
    finally:
        del VALIDATORS["fake"]


def test_an_unknown_source_type_is_rejected_by_name(
    client: tuple[TestClient, dict[str, str]],
) -> None:
    opened, admin = client
    # an unregistered tag, deliberately: `confluence` is a real variant, and
    # a test that used it would stop testing the discriminator and start
    # testing a body with missing fields.
    response = opened.post(
        "/sources",
        json={"name": "wiki", "type": "sharepoint", "space": SPACE},
        headers=admin,
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation-error"
    # the message must name what IS accepted, or the user is guessing
    assert "git" in str(body["error"]["details"])


def test_a_source_type_is_a_variant_and_a_table_entry(
    extended: tuple[TestClient, dict[str, str], list[str]],
) -> None:
    opened, admin, validated = extended

    created = opened.post(
        "/fake-sources",
        json={"name": "wiki", "type": "fake", "space": SPACE},
        headers=admin,
    )
    assert created.status_code == 201
    assert validated == [SPACE]  # its own validator ran, dispatched by type

    fetched = opened.get("/fake-sources/wiki", headers=admin)
    assert fetched.status_code == 200
    assert fetched.json() == {"name": "wiki", "type": "fake", "space": SPACE}


def test_a_variant_without_auth_stores_and_reads_back_clean(
    extended: tuple[TestClient, dict[str, str], list[str]],
) -> None:
    # `sources` declares `auth.token` / `auth.key` secret; a variant with no
    # auth at all must not trip the encrypt/mask walk on a path it lacks.
    opened, admin, _ = extended
    opened.post(
        "/fake-sources",
        json={"name": "wiki", "type": "fake", "space": SPACE},
        headers=admin,
    )

    listed = opened.get("/fake-sources", headers=admin).json()
    assert [item["space"] for item in listed] == [SPACE]
    assert "***" not in str(listed)


def test_git_keeps_its_validator() -> None:
    # the dispatch must not quietly drop git's reach check. Driven through
    # `validate_source` with git's own probe injected, so it proves the routing
    # and not the network.
    probed: list[str] = []

    def probe(
        url: str, env: dict[str, str], config_args: list[str], timeout: float
    ) -> tuple[int, str]:
        probed.append(url)
        return 128, "repository not found"

    config = {
        "name": "repo",
        "type": "git",
        "url": "https://example.invalid/nope.git",
        "auth": {"method": "none"},
    }
    with pytest.raises(ValidationFailed):
        VALIDATORS["git"](config, None, run=probe)  # type: ignore[call-arg]
    assert probed == ["https://example.invalid/nope.git"]
    assert VALIDATORS["git"] is validate_git


def test_a_type_with_no_validator_registers_without_a_reach_check() -> None:
    # config is data you PUT: a reader hrono cannot probe yet is still a
    # legitimate declaration, and its sync fails loudly later if it is wrong.
    validate_source({"name": "wiki", "type": "unprobed"}, None)


def test_a_git_url_that_starts_with_a_dash_is_a_422_naming_the_field(
    client: tuple[TestClient, dict[str, str]],
) -> None:
    # `--upload-pack=<cmd>` would reach git as an option. Refused at the
    # boundary: nothing stored, and the hook (which runs git) never reached.
    opened, admin = client
    response = opened.post(
        "/sources",
        json={
            "name": "evil",
            "type": "git",
            "url": "--upload-pack=touch /tmp/x",
            "auth": {"method": "none"},
        },
        headers=admin,
    )

    assert response.status_code == 422
    assert "url" in str(response.json()["error"]["details"])
    assert opened.get("/sources/evil", headers=admin).status_code == 404
