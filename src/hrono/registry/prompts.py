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


_DEFAULTS: tuple[dict[str, object], ...] = (
    {
        "name": "condense",
        "role": "condense",
        "template": (
            "Condense the section below to its essential information. Length "
            "follows content density: collapse boilerplate to a line, keep "
            "dense logic. Copy identifiers and values VERBATIM — never infer "
            "them. Add a line prefixed 'GOTCHA:' for anything non-obvious that "
            "could hurt a newcomer.\n\n{content}"
        ),
    },
    {
        "name": "brief",
        "role": "brief",
        "template": (
            "State what this group of condensations is as a whole, then "
            "surface the natural groupings actually present — never force a "
            "structure. Use concrete names; compress near-identical items into "
            "a pattern plus its variations. End with a 'Caution:' section "
            "aggregating any GOTCHA lines, omitted when there are none."
            "\n\n{content}"
        ),
    },
    {
        "name": "brief-upper",
        "role": "brief-upper",
        "template": (
            "Summarize the child briefs below into one higher-level brief for "
            "a parent node. Keep concrete names and routing signal; drop "
            "detail that only matters within a single child.\n\n{content}"
        ),
    },
    {
        "name": "judge",
        "role": "judge",
        "template": (
            "Rank the candidate summary against the source for faithfulness "
            "and usefulness. Flag any identifier or value in the summary that "
            "does not appear in the source.\n\nSource:\n{source}\n\n"
            "Summary:\n{summary}"
        ),
    },
)


PROMPTS = Descriptor(
    collection="prompts",
    model=Prompt,
    secret_paths=(),
    write_role="writer",
    validate=_validate,
    defaults=_DEFAULTS,
)
