"""The ``prompts`` collection: prompt templates typed by pipeline role.

Secretless: a descriptor plus a pydantic model on the generic registry engine.
Each role has a seeded default, which a delete resets rather than removes; the
validation hook refuses a template missing its role's placeholders.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from hrono.registry.descriptor import (
    Descriptor,
    RegistryName,
    ValidationContext,
    ValidationFailed,
)


class Prompt(BaseModel):
    name: RegistryName = Field(
        title="Name", description="What this prompt is called."
    )
    role: Literal["condense", "brief", "brief-upper", "judge"] = Field(
        title="Role",
        description="The writing job that sends it. One prompt per role.",
    )
    template: str = Field(
        title="Template",
        description=(
            "The instruction sent with each call. Keep the placeholders its "
            "role fills: {content}, or {source} and {summary} for judge."
        ),
    )


# The placeholder each role's op injects the body at, so a stored template that
# drops it can never silently no-op the ``template.replace`` the summarize ops
# do. Data-driven (role -> required tokens), not a per-role branch. ``judge``
# is the propagate cascade's prompt, which injects {source} and {summary}.
_REQUIRED_PLACEHOLDERS: dict[str, tuple[str, ...]] = {
    "condense": ("{content}",),
    "brief": ("{content}",),
    "brief-upper": ("{content}",),
    "judge": ("{source}", "{summary}"),
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


# The defaults are the prompts the research settled on
# (docs/summarization.md; docs/research/prototype/): the condense prompt of
# tree-level1.ipynb, the adaptive-gotchas brief of summarize_experiments.py,
# the round-7 upper prompt of summarize-level2-experiments.ipynb and the
# relevance judge of update-threshold.ipynb. Each op appends its content at
# the placeholder.
_CONDENSE = """\
Condense this content chunk to its essential information. Let the length \
follow the density of the content: boilerplate, generated, or repetitive \
content collapses to one short line saying so; dense logic keeps whatever it \
needs to stay faithful. Copy concrete identifiers, names, values, and \
constraints VERBATIM from the content - never infer or add ones that are not \
literally there. If the content holds anything non-obvious a newcomer could \
be hurt by (behavior differing from what names suggest, silent no-ops, \
partial or non-transactional operations, asymmetries, workarounds, fragile \
special cases), add a line starting with 'GOTCHA:' for each - only if \
literally present. Output only the condensed content.

{content}"""

_BRIEF = """\
Summarize the following group of related content chunks. The summary is a \
node in a knowledge tree: a reader (human or AI agent) uses it to understand \
what this group is and contains, without opening the chunks.

Guidelines:
- Start by stating what this group is as a whole and what \
domain/technology/format it belongs to, if any is apparent.
- Look at the content and identify the natural groupings or patterns actually \
present in it - whatever they are. Organize the summary by them, one section \
per grouping. Choose the structure that fits THIS content; do not force one.
- Describe each part with the concrete names and terms that appear in it.
- If many chunks are near-identical or repetitive, describe the pattern once \
and note the variation, instead of describing each.
- End with a "Caution" section listing anything non-obvious a newcomer could \
be hurt by: behavior differing from what names suggest, silent no-ops, partial \
or non-transactional operations, asymmetries, workarounds, fragile special \
cases. Omit the section entirely if there is nothing to warn about.
- Mention only what is actually present in the content - do not invent \
anything.

Output only the summary in markdown, nothing else.

{content}"""

_BRIEF_UPPER = """\
Each text below is the summary of one group of related content. Together the \
groups form one larger area. Write the summary of that whole area - one level \
of abstraction higher than the texts.

These are content requirements only - they say what the summary must convey, \
and they must not be recognizable in its form:
- what the area is as a whole;
- what only becomes visible when the groups are seen together: shared \
conventions, recurring patterns, emergent rules, invariants, cross-cutting \
decisions - never restating what a single text already says;
- the components someone would search for first, by name;
- hazards from the texts' caution notes, where they matter for the whole area.

The form is completely free: use whatever markdown serves this particular \
content best - headings, lists, tables, prose, or any mix. If you use \
headings, name them after the content's own concepts, never after the \
requirements above. Be substantially shorter than any of the texts; the \
length must not grow with the number of input texts. Never invent or \
generalize names. Output only the summary in markdown.

{content}"""

_JUDGE = """\
Below is the current summary of an area of a codebase, followed by the area's \
content as it is now, after a change somewhere within it. Judge whether the \
change affects the summary:
- "none": everything the summary says remains accurate and complete
- "minor": a small detail of the summary should change (a value, a name, one \
local fact)
- "major": statements in the summary become wrong, or important new facts now \
belong in it
Judge only against what the summary says or clearly should say at its level \
of detail. Reply with the one word first (none, minor or major), then a \
one-line reason.

CURRENT SUMMARY:
{summary}

CONTENT NOW:
{source}"""

_DEFAULTS: tuple[dict[str, object], ...] = (
    {"name": "condense", "role": "condense", "template": _CONDENSE},
    {"name": "brief", "role": "brief", "template": _BRIEF},
    {"name": "brief-upper", "role": "brief-upper", "template": _BRIEF_UPPER},
    {"name": "judge", "role": "judge", "template": _JUDGE},
)


PROMPTS = Descriptor(
    collection="prompts",
    model=Prompt,
    secret_paths=(),
    write_role="writer",
    validate=_validate,
    defaults=_DEFAULTS,
)
