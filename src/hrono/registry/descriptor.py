"""The per-collection descriptor the registry engine is driven by.

Each config collection (sources, connections, models, prompts) is one
``Descriptor`` (data); the engine walks it to build a uniform CRUD surface, so a
new collection is a descriptor, never a new branch in the engine.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from hrono.crypto.cipher import Cipher
from hrono.db.database import Database
from hrono.errors import BadRequest


class ValidationFailed(BadRequest):
    """A write was rejected by a collection's validation hook (maps to 400)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ValidationContext:
    """What a validation hook may need beyond the config it is validating.

    A hook can read a sibling collection (e.g. resolve a referenced connection)
    through ``database`` and decrypt that row's secret with ``cipher``.
    """

    database: Database
    cipher: Cipher


@dataclass(frozen=True)
class Descriptor:
    collection: str
    model: type[BaseModel]
    secret_paths: tuple[tuple[str, ...], ...]
    write_role: str
    validate: Callable[[dict[str, object], ValidationContext], None] | None = (
        None
    )
    defaults: tuple[dict[str, object], ...] = ()
