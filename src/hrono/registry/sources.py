"""The ``sources`` collection: declarative git repo config (T7.1).

Registering a source stores config only; nothing is pulled. Reach + auth
validation fills the descriptor's hook in a follow-up (#013).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from hrono.registry.descriptor import Descriptor


class GitAuth(BaseModel):
    method: Literal["none", "token", "ssh"]
    token: str | None = None
    key: str | None = None


class GitFilter(BaseModel):
    exclude: list[str] | None = None
    max_size_mb: float | None = None


class GitSource(BaseModel):
    name: str
    type: Literal["git"]
    url: str
    auth: GitAuth
    filter: GitFilter | None = None


def _validate(config: dict[str, object]) -> None:
    """Reach + auth validation lands in #013; the hook seam is wired here."""
    return None


SOURCES = Descriptor(
    collection="sources",
    model=GitSource,
    secret_paths=(("auth", "token"), ("auth", "key")),
    write_role="writer",
    validate=_validate,
)
