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

from hrono.registry.descriptor import Descriptor, RegistryName
from hrono.registry.validation.source_validation import validate_source

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


def _reject_reserved(value: str) -> str:
    """`node-` is hrono's own source namespace, not a user's (#076)."""
    if value.lower().startswith(RESERVED_PREFIX):
        raise ValueError(
            f"source names starting with {RESERVED_PREFIX!r} are reserved "
            f"for hrono's own brief passages"
        )
    return value


class GitSource(BaseModel):
    name: RegistryName
    type: Literal["git"]
    url: str
    auth: GitAuth
    filter: GitFilter | None = None

    _not_reserved = field_validator("name")(_reject_reserved)


class GithubUserSource(BaseModel):
    """An owner's repos, discovered through the provider API (T41.2).

    ``owner`` is a github username or org; the optional globs filter REPO
    NAMES, not paths — a source's file filter is the git type's job and applies
    to every discovered clone unchanged.
    """

    name: RegistryName
    type: Literal["github-user"]
    owner: str
    auth: GitAuth
    include: list[str] | None = None
    exclude: list[str] | None = None
    filter: GitFilter | None = None

    _not_reserved = field_validator("name")(_reject_reserved)


class BitbucketWorkspaceSource(BaseModel):
    """A workspace's repos, discovered through the provider API (T41.1).

    Same shape as ``GithubUserSource`` — ``owner`` is the workspace slug — and
    deliberately a separate variant rather than a shared model with a provider
    field: the discriminator IS the provider, and one type per provider is what
    lets the tables dispatch without a second branch inside them.
    """

    name: RegistryName
    type: Literal["bitbucket-workspace"]
    owner: str
    auth: GitAuth
    include: list[str] | None = None
    exclude: list[str] | None = None
    filter: GitFilter | None = None

    _not_reserved = field_validator("name")(_reject_reserved)


class BasicAuth(BaseModel):
    """Atlassian's api-token scheme: the account email plus a token."""

    method: Literal["basic"]
    email: str
    token: str


class Selector(BaseModel):
    """One scope selector; the fields it needs depend on its own type."""

    type: str
    key: str | None = None
    id: str | None = None


class ConfluenceSource(BaseModel):
    """Pages from a confluence site, narrowed by a union of selectors (T42)."""

    name: RegistryName
    type: Literal["confluence"]
    base_url: str
    auth: BasicAuth
    scope: list[Selector] | None = None

    _not_reserved = field_validator("name")(_reject_reserved)


class TokenAuth(BaseModel):
    """A bearer integration token; no user, no endpoint."""

    method: Literal["token"]
    token: str


class NotionSource(BaseModel):
    """Pages shared with a notion integration (T43).

    No base url — always api.notion.com — and no owner: an integration sees
    exactly what has been shared with it, so the token IS the scope's outer
    bound and the selectors only narrow it.
    """

    name: RegistryName
    type: Literal["notion"]
    auth: TokenAuth
    scope: list[Selector] | None = None

    _not_reserved = field_validator("name")(_reject_reserved)


class Source(
    RootModel[
        Annotated[
            GitSource
            | GithubUserSource
            | BitbucketWorkspaceSource
            | ConfluenceSource
            | NotionSource,
            Field(discriminator="type"),
        ]
    ]
):
    """A source, discriminated by its ``type`` (#141).

    The union is the point: a reader M8 adds is a model variant plus table
    entries, with no change to the registry engine that stores it —
    ``github-user`` (#147) was exactly that. An unknown ``type`` is rejected
    here, by pydantic, with the known tags in the message, and the engine turns
    that into a 422 like any other invalid body.
    """


SOURCES = Descriptor(
    collection="sources",
    model=Source,
    secret_paths=(("auth", "token"), ("auth", "key")),
    write_role="writer",
    validate=validate_source,
)
