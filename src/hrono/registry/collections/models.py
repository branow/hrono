"""The ``models`` collection: usage config for a text or embedding model (T9.1).

Secretless — the provider credential lives on the referenced ``connection``, so
``secret_paths`` is empty and the base does no encryption or masking. Load /
round-trip validation is the follow-on (#019); the hook seam is a no-op here.

``role`` maps a text model to the summarisation stage that should call it —
condense cheap, brief smart, judge cheap (#067). It is OPTIONAL and the
sole-text-model fallback is unchanged, so a one-model install needs no role at
all; the field exists so a two-model install is expressible without inventing a
second configuration mechanism beside the registry.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from hrono.registry.descriptor import Descriptor, RegistryName
from hrono.registry.validation.model_validation import validate_model

SummarisationRole = Literal["condense", "brief", "brief-upper", "judge"]


class ModelPrice(BaseModel):
    """USD per million tokens, overriding the baked table (#202)."""

    input: float = Field(ge=0)
    output: float = Field(ge=0)
    cache_read: float = Field(default=0.0, ge=0)
    cache_write: float = Field(default=0.0, ge=0)


class Model(BaseModel):
    name: RegistryName
    kind: Literal["text", "embedding"]
    connection: str | None = None
    model: str
    role: SummarisationRole | None = None
    params: dict[str, object] = Field(default_factory=dict)
    price: ModelPrice | None = None


MODELS = Descriptor(
    collection="models",
    model=Model,
    secret_paths=(),
    write_role="writer",
    validate=validate_model,
)
