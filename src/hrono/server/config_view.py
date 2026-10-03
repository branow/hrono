"""The config page's tables: every registry collection, secrets masked (#187).

Each collection is read as a TABLE with columns named for what an operator
tells its rows apart by (#210): models by role, connection and upstream model,
sources by type, location and which files. A run-on line of every scalar field
("kind text, connection cc, model sonnet, role brief") was the earlier answer,
and it read as config rather than as a list.

Kept out of the route so the pairing that matters — each row masked by ITS OWN
collection's descriptor — is testable. Today every declared secret path happens
to live in `sources`' set, so masking every row with the wrong descriptor still
produces a correct page; passing `descriptors` in makes the pairing observable
now rather than on the day a collection declares a path nobody else has.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from hrono.registry import store
from hrono.registry.collections import COLLECTIONS
from hrono.registry.descriptor import Descriptor
from hrono.registry.write import mask

# How much of one value a table cell may carry before it stops being
# scannable: one of the columns is a prompt template.
VALUE = 60


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

    def cells(self, collection: str) -> tuple[str, ...]:
        """This row's value under each of its collection's named columns."""
        return tuple(
            _short(column.read(self.data))
            for column in COLUMNS.get(collection, ())
        )


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


@dataclass(frozen=True)
class Column:
    """One named column, and how a row's config is read into it."""

    heading: str
    read: Callable[[Mapping[str, object]], str]


def _at(data: Mapping[str, object], path: str) -> object:
    here: object = data
    for part in path.split("."):
        if not isinstance(here, Mapping):
            return None
        here = here.get(part)
    return here


def _text(path: str, absent: str = "") -> Callable[[Mapping[str, object]], str]:
    """A column that is one field's value, or ``absent`` when it is unset."""

    def read(data: Mapping[str, object]) -> str:
        value = _at(data, path)
        return absent if value in (None, "") else str(value)

    return read


def _listed(data: Mapping[str, object]) -> str:
    return ", ".join(str(name) for name in data.get("sources") or ())


def _role(data: Mapping[str, object]) -> str:
    """A text model with no role serves any role; an embedding model none."""
    if data.get("role"):
        return str(data["role"])
    return "any" if data.get("kind") == "text" else "\u2014"


def _location(data: Mapping[str, object]) -> str:
    """Where a source reads from, whichever field its type keeps that in."""
    for key in ("url", "owner", "base_url"):
        if data.get(key):
            return str(data[key])
    return "everything shared with the integration"


def _which_files(data: Mapping[str, object]) -> str:
    """The filter layers, said briefly; no layer at all is every file."""
    said = []
    layers = data.get("filter")
    if isinstance(layers, Mapping):
        for key in ("only", "exclude", "include"):
            globs = layers.get(key)
            if globs:
                said.append(f"{key} {', '.join(map(str, globs))}")  # type: ignore[call-overload]
    for key in ("include", "exclude"):
        repos = data.get(key)
        if repos:
            said.append(f"repos {key} {', '.join(map(str, repos))}")  # type: ignore[call-overload]
    scope = data.get("scope")
    if scope:
        said.append(f"{len(scope)} selector(s)")  # type: ignore[arg-type]
    return "; ".join(said) or "every file"


COLUMNS: dict[str, tuple[Column, ...]] = {
    "trees": (Column("Sources", _listed),),
    "sources": (
        Column("Type", _text("type")),
        Column("Location", _location),
        Column("Access", _text("auth.method")),
        Column("Which files", _which_files),
    ),
    "connections": (
        Column("Provider", _text("provider")),
        Column("Endpoint", _text("endpoint", "the provider's own")),
        Column("Access", _text("auth.method")),
    ),
    "models": (
        Column("Kind", _text("kind")),
        Column("Role", _role),
        Column("Connection", _text("connection", "none")),
        Column("Upstream model", _text("model")),
    ),
    "prompts": (
        Column("Role", _text("role")),
        Column("Template", _text("template")),
    ),
}
