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

# How much of one value, and of a whole row, a scannable list may carry.
VALUE = 40
LINE = 110


def _short(value: object, limit: int = VALUE) -> str:
    """One value, on one line, cut where it stops being scannable."""
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "\u2026"


@dataclass(frozen=True)
class Row:
    name: str
    is_default: bool
    data: dict[str, object]

    @property
    def config(self) -> str:
        """The item as the JSON an operator reads and edits."""
        return json.dumps(self.data, indent=2)

    @property
    def summary(self) -> str:
        """The row's own identifying fields, for a list that is scannable.

        A list of names alone cannot be read: four models called `cc-*` are
        told apart by what they POINT AT, not by their names. Taken from the
        config's own scalar fields rather than from a per-collection template,
        so a collection added later is listed without a second edit (#200).

        Each value is cut, because one of these fields is a prompt template:
        printed whole it is a paragraph per row, and a list where every row is
        a paragraph is the wall this view exists to replace.
        """
        said = ", ".join(
            f"{key} {_short(value)}"
            for key, value in self.data.items()
            if key != "name"
            and isinstance(value, (str, int, float))
            and str(value)
        )
        return _short(said, LINE)


@dataclass(frozen=True)
class Table:
    name: str
    rows: tuple[Row, ...]

    @property
    def document(self) -> str:
        """The WHOLE collection as one JSON array.

        What an operator edits when they want to add a model rather than
        change one: the list is the thing, and `engine.sync_items` writes what
        differs and removes what is gone (#200).
        """
        return json.dumps([row.data for row in self.rows], indent=2)


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
                    data=mask(json.loads(row["config"]), descriptor),
                )
                for row in store.list_all(conn, descriptor.collection)
            ),
        )
        for descriptor in descriptors
    )
