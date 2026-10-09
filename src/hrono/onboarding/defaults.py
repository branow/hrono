"""What a first install registers, per provider.

One text model per writing role, because a role resolves to exactly one model:
the cheap one condenses (it runs once per section) and the stronger one writes
the briefs (it runs once per topic). A person who wants one model for
everything edits the upstream ids on the form, or Settings.
"""

from __future__ import annotations

from dataclasses import dataclass

EMBEDDING_NAME = "embedder"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# role -> which of the two tiers answers it
ROLES: dict[str, str] = {
    "condense": "cheap",
    "brief": "smart",
    "brief-upper": "smart",
    "judge": "cheap",
}


@dataclass(frozen=True)
class Provider:
    """One way to reach a text model that the setup path offers."""

    name: str
    label: str
    says: str
    needs_key: bool
    tiers: dict[str, str]


PROVIDERS: tuple[Provider, ...] = (
    Provider(
        name="claude-code",
        label="Claude Code (your Claude subscription)",
        says=(
            "Needs no API key and bills through your Claude subscription, so "
            "it is the way to try hrono out and to keep a tree current. Every "
            "call carries a large fixed overhead, so a first build over a "
            "large repository is slow and is better run on an API key."
        ),
        needs_key=False,
        tiers={"cheap": "haiku", "smart": "sonnet"},
    ),
    Provider(
        name="anthropic",
        label="Anthropic API (an API key)",
        says=(
            "Bills per token to the key you enter. It pays for the content "
            "rather than the harness, so it is cheaper and faster for a first "
            "build over a large repository."
        ),
        needs_key=True,
        tiers={"cheap": "claude-haiku-4-5", "smart": "claude-sonnet-5-5"},
    ),
)


def provider(name: str) -> Provider | None:
    return next((one for one in PROVIDERS if one.name == name), None)


def models_for(provider_name: str, connection: str) -> list[dict[str, object]]:
    """The embedding model and one text model per role, ready to register.

    A provider the setup path does not know gets the same rows with no
    upstream id, for the person to fill in.
    """
    known = provider(provider_name)
    tiers = known.tiers if known is not None else {}
    return [
        {
            "name": EMBEDDING_NAME,
            "kind": "embedding",
            "model": EMBEDDING_MODEL,
        },
        *(
            {
                "name": role,
                "kind": "text",
                "connection": connection,
                "model": tiers.get(tier, ""),
                "role": role,
            }
            for role, tier in ROLES.items()
        ),
    ]
