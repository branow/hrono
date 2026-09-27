"""#054: the ``trees`` collection — which sources a tree is the map over.

A tree with no entry is UNSCOPED, not empty: that distinction is the whole
reason this collection is additive, and it is what `sources_of` returning None
rather than `()` expresses.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.registry import store as registry_store
from hrono.registry.collections.trees import scoped_sources, sources_of
from hrono.server.app import create_app

KEY = Fernet.generate_key()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[tuple[TestClient, dict, object]]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    for name in ("alpha-src", "beta-src"):
        registry_store.insert(
            conn,
            "sources",
            name,
            json.dumps(
                {
                    "name": name,
                    "type": "git",
                    "url": f"https://example.com/{name}.git",
                    "auth": None,
                }
            ),
            None,
            "t",
        )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as http:
        yield http, {"Authorization": f"Bearer {token}"}, conn
    conn.close()


def test_a_tree_declares_the_sources_it_maps(
    client: tuple[TestClient, dict, object],
) -> None:
    http, headers, conn = client

    response = http.put(
        "/trees/alpha",
        json={"name": "alpha", "sources": ["alpha-src"]},
        headers=headers,
    )

    assert response.status_code in (200, 201), response.json()
    assert sources_of(conn, "alpha") == ("alpha-src",)  # type: ignore[arg-type]


def test_an_undeclared_tree_is_unscoped_not_empty(
    client: tuple[TestClient, dict, object],
) -> None:
    # None means "every embedded section", which is what every database built
    # before this collection existed already does. An empty tuple would mean
    # "no sections" and would silently empty those trees.
    _http, _headers, conn = client

    assert sources_of(conn, "nobody-declared-me") is None  # type: ignore[arg-type]
    assert set(scoped_sources(conn, "nobody-declared-me")) == {  # type: ignore[arg-type]
        "alpha-src",
        "beta-src",
    }


def test_a_tree_naming_an_unregistered_source_is_refused(
    client: tuple[TestClient, dict, object],
) -> None:
    # a tree whose source does not exist builds an empty map and reports
    # success, which is #132's failure: an op that declines work and says it
    # worked.
    http, headers, conn = client

    response = http.put(
        "/trees/ghost",
        json={"name": "ghost", "sources": ["alpha-src", "no-such-src"]},
        headers=headers,
    )

    assert response.status_code == 400
    assert "no-such-src" in response.json()["error"]["message"]
    assert sources_of(conn, "ghost") is None  # type: ignore[arg-type]


def test_a_tree_must_name_at_least_one_source(
    client: tuple[TestClient, dict, object],
) -> None:
    http, headers, _conn = client

    response = http.put(
        "/trees/empty",
        json={"name": "empty", "sources": []},
        headers=headers,
    )

    assert response.status_code == 422


def test_scoped_sources_drops_a_source_that_was_deleted(
    client: tuple[TestClient, dict, object],
) -> None:
    # validation catches an unknown source at write time; a source deleted
    # afterwards must not resurrect as an ingest target.
    http, headers, conn = client
    http.put(
        "/trees/alpha",
        json={"name": "alpha", "sources": ["alpha-src", "beta-src"]},
        headers=headers,
    )

    registry_store.delete(conn, "sources", "beta-src")  # type: ignore[arg-type]

    assert scoped_sources(conn, "alpha") == ("alpha-src",)  # type: ignore[arg-type]


def test_deleting_a_built_tree_s_config_says_what_it_arms(
    client: tuple[TestClient, dict, object],
) -> None:
    """#167: one small row, a corpus-wide recluster, and nothing said so.

    An absent row means UNSCOPED, which is the right meaning — so the next
    `maintain` on a tree whose config is gone clusters EVERY source into it.
    """
    http, headers, conn = client
    http.put(
        "/trees/alpha",
        json={"name": "alpha", "sources": ["alpha-src"]},
        headers=headers,
    )
    with conn:  # type: ignore[union-attr]
        conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES ('alpha', 0, 0, 't')"
        )

    response = http.delete("/trees/alpha", headers=headers)

    assert response.status_code == 200
    note = response.json()["note"]
    assert "EVERY source" in note
    assert "1 topic(s)" in note
    assert sources_of(conn, "alpha") is None  # type: ignore[arg-type]


def test_deleting_an_unbuilt_tree_s_config_is_quiet(
    client: tuple[TestClient, dict, object],
) -> None:
    # nothing has been built into it, so there is no consequence to warn about
    # and a note every time would be noise that teaches people to skip notes.
    http, headers, _conn = client
    http.put(
        "/trees/alpha",
        json={"name": "alpha", "sources": ["alpha-src"]},
        headers=headers,
    )

    response = http.delete("/trees/alpha", headers=headers)

    assert response.status_code == 200
    assert "note" not in response.json()


def test_a_collection_with_no_hook_deletes_exactly_as_before(
    client: tuple[TestClient, dict, object],
) -> None:
    # the hook is data on the descriptor; a collection that declares none must
    # behave byte-for-byte as it did.
    http, headers, _conn = client

    response = http.delete("/sources/beta-src", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"deleted": "beta-src"}
