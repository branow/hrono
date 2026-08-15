"""The ``models`` collection: usage config for a text or embedding model (T9.1).

Secretless — the provider credential lives on the referenced ``connection``, so
``secret_paths`` is empty and the base does no encryption or masking. Load /
round-trip validation is the follow-on (#019); the hook seam is a no-op here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from hrono.registry.descriptor import Descriptor


class Model(BaseModel):
    name: str
    kind: Literal["text", "embedding"]
    connection: str | None = None
    model: str
    params: dict[str, object] = Field(default_factory=dict)


def _validate(config: dict[str, object]) -> None:
    """Load / round-trip validation lands in #019; the seam is wired here."""
    return None


MODELS = Descriptor(
    collection="models",
    model=Model,
    secret_paths=(),
    write_role="writer",
    validate=_validate,
)
