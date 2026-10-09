"""Each collection's rows are masked by ITS OWN declared secret paths.

Through the route this is unobservable today: every path any collection
declares also lives in `sources`' set, so masking everything with the wrong
descriptor still renders a correct page. Descriptors are passed in here so the
pairing is asserted directly, before the day a collection declares a path
nobody else has and the page quietly starts printing a credential.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from hrono.db.database import open_database
from hrono.registry import store
from hrono.registry.collections import COLLECTIONS
from hrono.registry.descriptor import Descriptor
from hrono.registry.write import MASK
from hrono.server import config_view


class _Any(BaseModel):
    name: str


def _descriptor(collection: str, *paths: tuple[str, ...]) -> Descriptor:
    return Descriptor(
        collection=collection,
        model=_Any,
        secret_paths=paths,
        write_role="writer",
    )


@pytest.fixture
def conn(tmp_path: Path):  # type: ignore[no-untyped-def]
    connection = open_database(tmp_path / "hrono.db")
    yield connection
    connection.close()


def test_a_row_is_masked_by_its_own_collections_paths(conn) -> None:  # type: ignore[no-untyped-def]
    store.insert(
        conn, "sources", "a", json.dumps({"auth": {"token": "t"}}), None, "t"
    )
    store.insert(
        conn, "connections", "b", json.dumps({"auth": {"pass": "p"}}), None, "t"
    )

    tables = config_view.tables(
        conn,
        (
            _descriptor("sources", ("auth", "token")),
            _descriptor("connections", ("auth", "pass")),
        ),
    )

    assert json.loads(tables[0].rows[0].config)["auth"]["token"] == MASK
    assert json.loads(tables[1].rows[0].config)["auth"]["pass"] == MASK


def test_one_collections_paths_are_not_applied_to_another(conn) -> None:  # type: ignore[no-untyped-def]
    """The mutation the route cannot see: the wrong descriptor for every row.

    `connections` declares `auth.pass` and `sources` does not, so a page built
    with `sources`' descriptor for both leaves `p` in the second table.
    """
    store.insert(
        conn, "connections", "b", json.dumps({"auth": {"pass": "p"}}), None, "t"
    )

    wrong = config_view.tables(
        conn, (_descriptor("connections", ("auth", "token")),)
    )

    assert json.loads(wrong[0].rows[0].config)["auth"]["pass"] == "p"


def test_the_default_descriptors_are_the_registered_ones(conn) -> None:  # type: ignore[no-untyped-def]
    # the route passes none, so the default IS the page's collection list
    assert tuple(table.name for table in config_view.tables(conn)) == tuple(
        descriptor.collection for descriptor in COLLECTIONS
    )
