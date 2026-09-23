"""The ``sources`` collection: source config, discriminated by type (T7.1).

Registering a source stores config only; nothing is pulled. Reach + auth
validation fills the descriptor's hook in a follow-up (#013).

THE ``node-`` PREFIX IS RESERVED (#076). Brief passages are stored under a
synthetic source key ``node-<id>`` (#071) in the same ``sources.source``
namespace a user registers into, and `store_brief` clears that key before
re-writing — so a user source literally named ``node-5`` would have its passages
and FTS rows wiped by node 5's next re-brief, and vice versa. Silent
cross-deletion, in a namespace the user has no reason to know is shared.

Reserving the prefix at the boundary is the smaller half of the two fixes the
ticket offered: it costs one validator and no migration, where re-namespacing
the brief keys would touch the passage store, the FTS index and every stored
row. The retirement direction is already closed by construction — #125's trigger
matches on ``source_type`` as well as name — so this is the remaining one.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, RootModel, field_validator

from hrono.registry.descriptor import Descriptor
from hrono.registry.source_validation import validate_source

RESERVED_PREFIX = "node-"


class GitAuth(BaseModel):
    method: Literal["none", "token", "ssh"]
    token: str | None = None
    key: str | None = None


class GitFilter(BaseModel):
    exclude: list[str] | None = None
    include: list[str] | None = None
    replace_defaults: bool = False
    include_generated: bool = False
    max_size_mb: float | None = None


class GitSource(BaseModel):
    name: str
    type: Literal["git"]
    url: str
    auth: GitAuth
    filter: GitFilter | None = None

    @field_validator("name")
    @classmethod
    def _not_reserved(cls, value: str) -> str:
        """`node-` is hrono's own source namespace, not a user's (#076)."""
        if value.lower().startswith(RESERVED_PREFIX):
            raise ValueError(
                f"source names starting with {RESERVED_PREFIX!r} are reserved "
                f"for hrono's own brief passages"
            )
        return value


class Source(RootModel[Annotated[GitSource, Field(discriminator="type")]]):
    """A source, discriminated by its ``type`` (#141).

    One variant today, and the union is the point: a reader M8 adds is a model
    variant plus a validator entry, with no change to the registry engine that
    stores it. An unknown ``type`` is rejected here, by pydantic, with the known
    tags in the message — the engine turns that into a 422 like any other
    invalid body.
    """


SOURCES = Descriptor(
    collection="sources",
    model=Source,
    secret_paths=(("auth", "token"), ("auth", "key")),
    write_role="writer",
    validate=validate_source,
)
