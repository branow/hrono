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

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, RootModel, field_validator

from hrono.registry.descriptor import Descriptor, RegistryName
from hrono.registry.validation.source_validation import validate_source

RESERVED_PREFIX = "node-"

# The three questions a source's form is grouped by (#210). Declared on the
# field, so the API's model and the dashboard's form are one schema: a field
# added to a source type lands in its group with no edit to the page.
LOCATION = {"group": "Location"}
ACCESS = {"group": "Access"}
FILES = {"group": "Which files"}


def _name() -> Any:
    return Field(
        title="Name",
        description=(
            "What this source is called in trees, on the map and on the "
            "command line. hrono keeps one name prefix for its own briefs, "
            "and a name that starts with it is refused."
        ),
    )


class GitAuth(BaseModel):
    method: Literal["none", "token", "ssh"] = Field(
        title="Sign-in method",
        description=(
            "none for a public repository, token for HTTPS with an access "
            "token, ssh for a deploy key."
        ),
    )
    token: str | None = Field(
        default=None,
        title="Access token",
        description=(
            "A token with read access, used when the method is token. Stored "
            "encrypted."
        ),
    )
    key: str | None = Field(
        default=None,
        title="SSH private key",
        description=(
            "A read-only deploy key, used when the method is ssh. Stored "
            "encrypted."
        ),
    )


class GitFilter(BaseModel):
    """The glob layers one source's files are chosen by (``ingest.filter``).

    ``only`` is the WHITELIST and is deliberately not called ``include``.
    ``include`` already exists and means something else — it RE-ADMITS what the
    baked ignore groups caught, one file at a time — so renaming it would
    silently change the meaning of every config already written, and giving the
    whitelist that name would make the two indistinguishable in a review. The
    cost of the missing layer was real: with no way to say "only this package",
    pointing hrono at a monorepo ingested all of it.

    Globs, not regex, because globs are what every tool a user already knows
    uses for paths, this module already matches ``**`` through
    ``PurePosixPath.full_match``, and a regex mistyped over a path fails open —
    in the direction that costs money.
    """

    only: list[str] | None = Field(
        default=None,
        title="Only these paths",
        description=(
            "Globs, one per line. When set, nothing outside them is read — "
            "the way to take one package of a monorepo."
        ),
        examples=["src/payments/**"],
    )
    exclude: list[str] | None = Field(
        default=None,
        title="Leave out",
        description=(
            "Globs, one per line, of paths to skip on top of the built-in "
            "ignore list."
        ),
        examples=["**/fixtures/**"],
    )
    include: list[str] | None = Field(
        default=None,
        title="Read anyway",
        description=(
            "Globs, one per line, of files the built-in ignore list would "
            "skip. Re-admits them; it is not a whitelist."
        ),
        examples=["vendor/our-client/**"],
    )
    replace_defaults: bool = Field(
        default=False,
        title="Drop the built-in ignore list",
        description=(
            "Skip only what Leave out names. The size, symlink and binary "
            "checks still apply."
        ),
    )
    include_generated: bool = Field(
        default=False,
        title="Read generated code",
        description=(
            "Keep the files the built-in list skips as generated, such as a "
            "generated API client."
        ),
    )
    max_size_mb: float | None = Field(
        default=None,
        title="Largest file, in MB",
        description="Files bigger than this are skipped. 2 MB when empty.",
    )


def _reject_reserved(value: str) -> str:
    """`node-` is hrono's own source namespace, not a user's (#076)."""
    if value.lower().startswith(RESERVED_PREFIX):
        raise ValueError(
            f"source names starting with {RESERVED_PREFIX!r} are reserved "
            f"for hrono's own brief passages"
        )
    return value


def _reject_option_url(value: str) -> str:
    """A leading "-" would reach git as an option, not a location."""
    if value.lstrip().startswith("-"):
        raise ValueError(
            "a repository URL cannot start with '-': git would read it "
            "as an option"
        )
    return value


class GitSource(BaseModel):
    name: RegistryName = _name()
    type: Literal["git"] = Field(
        title="Type", description="A single git repository."
    )
    url: str = Field(
        title="Repository URL",
        description="What git clone takes: an HTTPS or SSH URL, or a path.",
        examples=["https://github.com/acme/payments.git"],
        json_schema_extra=LOCATION,
    )
    auth: GitAuth = Field(
        title="Sign-in",
        description="How hrono authenticates to the host.",
        json_schema_extra=ACCESS,
    )
    filter: GitFilter | None = Field(
        default=None,
        title="File filter",
        description="Which files of each repository are read.",
        json_schema_extra=FILES,
    )

    _not_reserved = field_validator("name")(_reject_reserved)
    _not_option = field_validator("url")(_reject_option_url)


class GithubUserSource(BaseModel):
    """An owner's repos, discovered through the provider API (T41.2).

    ``owner`` is a github username or org; the optional globs filter REPO
    NAMES, not paths — a source's file filter is the git type's job and applies
    to every discovered clone unchanged.
    """

    name: RegistryName = _name()
    type: Literal["github-user"] = Field(
        title="Type", description="Every repository of a GitHub user or org."
    )
    owner: str = Field(
        title="Owner",
        description=(
            "The GitHub user or organisation whose repositories to read."
        ),
        json_schema_extra=LOCATION,
    )
    auth: GitAuth = Field(
        title="Sign-in",
        description="How hrono authenticates to the host.",
        json_schema_extra=ACCESS,
    )
    include: list[str] | None = Field(
        default=None,
        title="Only these repositories",
        description="Globs over repository names, one per line.",
        examples=["payments-*"],
        json_schema_extra=FILES,
    )
    exclude: list[str] | None = Field(
        default=None,
        title="Leave out repositories",
        description="Globs over repository names, one per line.",
        examples=["*-archive"],
        json_schema_extra=FILES,
    )
    filter: GitFilter | None = Field(
        default=None,
        title="File filter",
        description="Which files of each repository are read.",
        json_schema_extra=FILES,
    )

    _not_reserved = field_validator("name")(_reject_reserved)


class BitbucketWorkspaceSource(BaseModel):
    """A workspace's repos, discovered through the provider API (T41.1).

    Same shape as ``GithubUserSource`` — ``owner`` is the workspace slug — and
    deliberately a separate variant rather than a shared model with a provider
    field: the discriminator IS the provider, and one type per provider is what
    lets the tables dispatch without a second branch inside them.
    """

    name: RegistryName = _name()
    type: Literal["bitbucket-workspace"] = Field(
        title="Type", description="Every repository of a Bitbucket workspace."
    )
    owner: str = Field(
        title="Workspace",
        description="The Bitbucket workspace slug whose repositories to read.",
        json_schema_extra=LOCATION,
    )
    auth: GitAuth = Field(
        title="Sign-in",
        description="How hrono authenticates to the host.",
        json_schema_extra=ACCESS,
    )
    include: list[str] | None = Field(
        default=None,
        title="Only these repositories",
        description="Globs over repository names, one per line.",
        examples=["payments-*"],
        json_schema_extra=FILES,
    )
    exclude: list[str] | None = Field(
        default=None,
        title="Leave out repositories",
        description="Globs over repository names, one per line.",
        examples=["*-archive"],
        json_schema_extra=FILES,
    )
    filter: GitFilter | None = Field(
        default=None,
        title="File filter",
        description="Which files of each repository are read.",
        json_schema_extra=FILES,
    )

    _not_reserved = field_validator("name")(_reject_reserved)


class BasicAuth(BaseModel):
    """Atlassian's api-token scheme: the account email plus a token."""

    method: Literal["basic"] = Field(
        title="Sign-in method",
        description="Atlassian's account email plus an API token.",
    )
    email: str = Field(
        title="Account email",
        description="The Atlassian account the API token belongs to.",
    )
    token: str = Field(
        title="API token",
        description=(
            "An Atlassian API token for that account. Stored encrypted."
        ),
    )


class Selector(BaseModel):
    """One scope selector; the fields it needs depend on its own type."""

    type: str = Field(
        title="Selector",
        description=(
            "all; space, by key (Confluence); page or database, by id."
        ),
    )
    key: str | None = Field(
        default=None, title="Space key", description="For a space selector."
    )
    id: str | None = Field(
        default=None,
        title="Page or database id",
        description="For a page or database selector.",
    )


class ConfluenceSource(BaseModel):
    """Pages from a confluence site, narrowed by a union of selectors (T42)."""

    name: RegistryName = _name()
    type: Literal["confluence"] = Field(
        title="Type", description="Pages of a Confluence site."
    )
    base_url: str = Field(
        title="Site URL",
        description="The Confluence site's address.",
        examples=["https://acme.atlassian.net/wiki"],
        json_schema_extra=LOCATION,
    )
    auth: BasicAuth = Field(
        title="Sign-in",
        description="How hrono authenticates to the site.",
        json_schema_extra=ACCESS,
    )
    scope: list[Selector] | None = Field(
        default=None,
        title="Scope",
        description=(
            "A JSON list of selectors; empty reads everything the account "
            "can see."
        ),
        examples=['[{"type": "space", "key": "ENG"}]'],
        json_schema_extra=FILES,
    )

    _not_reserved = field_validator("name")(_reject_reserved)


class TokenAuth(BaseModel):
    """A bearer integration token; no user, no endpoint."""

    method: Literal["token"] = Field(
        title="Sign-in method", description="A Notion integration token."
    )
    token: str = Field(
        title="Integration token",
        description="The secret of a Notion integration. Stored encrypted.",
    )


class NotionSource(BaseModel):
    """Pages shared with a notion integration (T43).

    No base url — always api.notion.com — and no owner: an integration sees
    exactly what has been shared with it, so the token IS the scope's outer
    bound and the selectors only narrow it.
    """

    name: RegistryName = _name()
    type: Literal["notion"] = Field(
        title="Type", description="Pages shared with a Notion integration."
    )
    auth: TokenAuth = Field(
        title="Sign-in",
        description="How hrono authenticates to Notion.",
        json_schema_extra=ACCESS,
    )
    scope: list[Selector] | None = Field(
        default=None,
        title="Scope",
        description=(
            "A JSON list of selectors; empty reads everything shared with the "
            "integration."
        ),
        examples=['[{"type": "page", "id": "..."}]'],
        json_schema_extra=FILES,
    )

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
