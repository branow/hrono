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

    input: float = Field(
        ge=0, title="Input", description="USD per million input tokens."
    )
    output: float = Field(
        ge=0, title="Output", description="USD per million output tokens."
    )
    cache_read: float = Field(
        default=0.0,
        ge=0,
        title="Cache read",
        description="USD per million tokens read from the prompt cache.",
    )
    cache_write: float = Field(
        default=0.0,
        ge=0,
        title="Cache write",
        description="USD per million tokens written to the prompt cache.",
    )


class Model(BaseModel):
    name: RegistryName = Field(
        title="Name",
        description="What runs and the command line call this model.",
    )
    kind: Literal["text", "embedding"] = Field(
        title="Kind",
        description=(
            "text writes condensations and briefs; embedding places sections."
        ),
    )
    connection: str | None = Field(
        default=None,
        title="Connection",
        description=(
            "The connection it is called through. Empty for a local embedding"
            " model."
        ),
    )
    model: str = Field(
        title="Upstream model",
        description="The provider's own id for the model.",
        examples=["claude-sonnet-4-5"],
    )
    role: SummarisationRole | None = Field(
        default=None,
        title="Role",
        description=(
            "The writing job that calls it. Leave empty on a one-model install."
        ),
    )
    params: dict[str, object] = Field(
        default_factory=dict,
        title="Parameters",
        description="A JSON object passed with every call, such as max_tokens.",
    )
    price: ModelPrice | None = Field(
        default=None,
        title="Price",
        description="What it costs, overriding the built-in price table.",
    )


MODELS = Descriptor(
    collection="models",
    model=Model,
    secret_paths=(),
    write_role="writer",
    validate=validate_model,
)
