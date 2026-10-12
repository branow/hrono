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


# The defaults are the prompts the 2026-10 experiments on the bcreg corpus
# settled on: condense `purpose-decisions`
# (docs/evaluations/2026-10-condense-prompts/), the leaf brief `core-states`
# and the upper brief `area-flows` (docs/evaluations/2026-10-brief-prompts/),
# each scored against the verified facts of the agents evaluation. The judge
# is the relevance judge of update-threshold.ipynb. Each op appends its
# content at the placeholder.

_CONDENSE = """\
Condense this content chunk. Start with one sentence saying what it is for, \
in the terms of the system it belongs to: the job it does (for example \
"Applies a confirmed payment to its business filing"), not how it is built. \
If it is a test, fixture, configuration, build file, migration or \
documentation, say so in that first sentence and name what it serves.

Then give what a reader needs to find and change its behaviour: what comes \
in, what goes out and in what shape, the steps of its main flow, and every \
decision it makes - the condition, the outcome, and the function, constant, \
list or field that holds it. Name identifiers together with what they do, \
never as bare lists. Mechanism (frameworks, queues, retries, wiring) comes \
after the purpose. Boilerplate (licence headers, imports, logging and server \
setup, plain configuration) collapses to one short line, or to nothing. Aim \
for 60 to 120 words; a chunk with many decisions may use up to 250. Copy \
names and values VERBATIM from the content - never infer or add ones that \
are not literally there. If the code itself shows something a newcomer could \
be hurt by (an exception swallowed, a partial or non-transactional update, a \
hard-coded special case, behaviour differing from what a name says), add a \
line starting with 'GOTCHA:' for each. Never guess about spelling, naming or \
intent. Output only the condensed content.

{content}"""

_BRIEF = """\
Below are notes on the sources of one part of a larger system, each under \
its source's name. Write what a reader (human or AI agent) must know about \
this part to understand its role in the system and to find where to change \
it. The notes stay available below this description, so leave detail to \
them: keep what is fundamental, drop what is obvious or minor.

Keep, in this order:
1. One or two sentences: what this part does and what it hands work to or \
takes work from.
2. Its contract with the rest of the system: what reaches it and from where, \
what it sends or writes and to where, with the shape of messages or records \
that cross the boundary.
3. The decisions that shape its behaviour, one line each: the condition, the \
outcome, and the function, constant or list that holds it. Include every \
step that moves a record from one state to another (created, submitted, \
paid, reviewed, resubmitted, completed, deleted - whatever this part has) \
and every check that refuses a caller (authorization, validation, locks), \
naming the function that does it.
4. Hazards that lose, duplicate or corrupt work, or fail silently - at most \
three.
5. The two to four sources to open first, and what each holds.

Leave out: startup and wiring, configuration keys and defaults, lists of \
fields or enum values, health checks, version helpers, logging, test \
plumbing, and any hazard about style, naming or types. Name a test only when \
it pins down a behaviour from point 3. If the notes cover unrelated things, \
say so and give each its own short description.

Write compactly: one line per decision, no padding. Aim for 250 to 500 \
words; a part with several distinct jobs may use up to 800. Write about the \
part itself. Never describe the text you were given: no "this group", "this \
set", "these chunks", "the summaries", "condensed" or "the files above". Say \
what things do, never only that they exist: a name without what it does is \
noise. Licences, server and logging setup, environment defaults and \
packaging get one line at most, and only if they matter to a reader. Mention \
only what is actually present - do not invent anything.

Output only the description in markdown, nothing else.

{content}"""

_BRIEF_UPPER = """\
Below are descriptions of the parts of one area of a larger system, each \
under its title. Write what a reader (human or AI agent) must know about the \
whole area: what it does, and how work moves through its parts.

Open with one or two sentences: what this area does and what it hands work \
to or takes work from outside it. Then the end-to-end flows of the area - \
the things a user or another system asks of it - each as numbered steps from \
what starts it to what it ends with, naming at each step the part and the \
function that does it and the state the record moves to. Then one line per \
part not already named in a flow, saying its job. End with at most three \
hazards that come from how the parts interact.

Aim for 300 to 600 words, however many parts there are. Leave out what one \
part's description already says in detail - a reader opens that part for it \
- and setup, configuration, field lists and style hazards. Name a part by \
its title so a reader can open it. Mention only what the descriptions say - \
do not invent anything. Write about the part itself. Never describe the text \
you were given: no "this group", "this set", "these chunks", "the \
summaries", "condensed" or "the files above". Output only the description in \
markdown, nothing else.

{content}"""

_JUDGE = """\
Below is the current summary of an area of a codebase, followed by a change \
that occurred somewhere within it: the content added or changed, and the \
content removed (each shown condensed, under its file). Judge whether this \
change affects the summary:
- "none": everything the summary says remains accurate and complete
- "minor": a small detail of the summary should change (a value, a name, one \
local fact)
- "major": statements in the summary become wrong, or important new facts now \
belong in it
Judge only against what the summary says or clearly should say at its level \
of detail. Reply with exactly one word: none, minor or major.

CURRENT SUMMARY:
{summary}

THE CHANGE:
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
