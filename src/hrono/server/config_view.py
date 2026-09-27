"""The config page's tables: every registry collection, secrets masked (#187).

Kept out of the route so the pairing that matters — each row masked by ITS OWN
collection's descriptor — is testable. Today every declared secret path happens
to live in `sources`' set, so masking every row with the wrong descriptor still
produces a correct page; passing `descriptors` in makes the pairing observable
now rather than on the day a collection declares a path nobody else has.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from hrono.registry import store
from hrono.registry.collections import COLLECTIONS
from hrono.registry.descriptor import Descriptor
from hrono.registry.write import mask


@dataclass(frozen=True)
class Row:
    name: str
    is_default: bool
    config: str


@dataclass(frozen=True)
class Table:
    name: str
    rows: tuple[Row, ...]


def tables(
    conn: sqlite3.Connection,
    descriptors: Sequence[Descriptor] = COLLECTIONS,
) -> tuple[Table, ...]:
    """Every collection's items, each masked by its own declared paths."""
    return tuple(
        Table(
            name=descriptor.collection,
            rows=tuple(
                Row(
                    name=str(row["name"]),
                    is_default=bool(row["is_default"]),
                    config=json.dumps(
                        mask(json.loads(row["config"]), descriptor), indent=2
                    ),
                )
                for row in store.list_all(conn, descriptor.collection)
            ),
        )
        for descriptor in descriptors
    )
