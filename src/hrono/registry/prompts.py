"""The ``prompts`` collection: prompt templates typed by pipeline role (T10.1).

Fourth and final M1 collection — secretless, again a descriptor plus a pydantic
model on the #012 base. Default seeding and the default-reset-on-delete
semantics are the follow-on (#021); the validation hook is a no-op stub #021 may
fill for template sanity.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from hrono.registry.descriptor import Descriptor, ValidationContext


class Prompt(BaseModel):
    name: str
    role: Literal["condense", "brief", "brief-upper", "judge"]
    template: str


def _validate(config: dict[str, object], context: ValidationContext) -> None:
    """No external validation for a prompt; #021 may add template sanity."""
    return None


PROMPTS = Descriptor(
    collection="prompts",
    model=Prompt,
    secret_paths=(),
    write_role="writer",
    validate=_validate,
)
