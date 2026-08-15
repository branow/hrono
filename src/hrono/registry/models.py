"""The ``models`` collection: usage config for a text or embedding model (T9.1).

Secretless — the provider credential lives on the referenced ``connection``, so
``secret_paths`` is empty and the base does no encryption or masking. Load /
round-trip validation is the follow-on (#019); the hook seam is a no-op here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from hrono.registry.descriptor import Descriptor
from hrono.registry.model_validation import validate_model


class Model(BaseModel):
    name: str
    kind: Literal["text", "embedding"]
    connection: str | None = None
    model: str
    params: dict[str, object] = Field(default_factory=dict)


MODELS = Descriptor(
    collection="models",
    model=Model,
    secret_paths=(),
    write_role="writer",
    validate=validate_model,
)
