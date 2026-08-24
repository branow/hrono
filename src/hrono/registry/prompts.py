"""The ``prompts`` collection: prompt templates typed by pipeline role (T10.1).

Fourth and final M1 collection — secretless, again a descriptor plus a pydantic
model on the #012 base. Default seeding and the default-reset-on-delete
semantics are the follow-on (#021); the validation hook is a no-op stub #021 may
fill for template sanity.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from hrono.registry.descriptor import (
    Descriptor,
    ValidationContext,
    ValidationFailed,
)


class Prompt(BaseModel):
    name: str
    role: Literal["condense", "brief", "brief-upper", "judge"]
    template: str


# The placeholder each role's op injects the body at, so a stored template that
# drops it can never silently no-op the ``template.replace`` the summarize ops
# do. Data-driven (role -> required tokens), not a per-role branch. ``judge`` is
# omitted until its op (#063) settles the tokens it injects — we do not guard a
# token no op uses.
_REQUIRED_PLACEHOLDERS: dict[str, tuple[str, ...]] = {
    "condense": ("{content}",),
    "brief": ("{content}",),
    "brief-upper": ("{content}",),
}


def _validate(config: dict[str, object], context: ValidationContext) -> None:
    """Reject a template that omits a placeholder its role's op injects at."""
    role = str(config["role"])
    template = str(config["template"])
    missing = [
        token
        for token in _REQUIRED_PLACEHOLDERS.get(role, ())
        if token not in template
    ]
    if missing:
        raise ValidationFailed(
            f"{role} prompt template must contain " + ", ".join(missing)
        )


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
