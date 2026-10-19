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


# The defaults come from the 2026-10 experiments on the bcreg corpus
# (docs/evaluations/2026-10-defines-uses/, round 8), which traced each answer
# claim through the tree. Nothing below a brief is shown to an agent, so
# neither prompt has a word target: the condensation keeps every check, branch,
# list, loop, error path and call out (the `ledger2` prompt), and the brief
# keeps them all for its reader (the `W` prompt). The upper brief does keep a
# range: its children's briefs sit below it in the map, and without one the
# root of the bcreg sub-tree ran to 13,600 words (round 9). Both say what the
# code does, never what a name suggests. The judge is the relevance judge of
# update-threshold.ipynb. Each op appends its content at the placeholder.

_CONDENSE = """\
Condense this content chunk. The condensation is what the brief of its topic \
is written from, in place of the chunk: a writer must be able to answer exact \
questions about the chunk from the condensation alone.

Start with one sentence saying what it is for, in the terms of the system it \
belongs to: the job it does (for example "Applies a confirmed payment to its \
business filing"), not how it is built. If it is a test, fixture, \
configuration, build file, migration or documentation, say so in that first \
sentence and name what it serves.

Then, for code, keep every one of these that the chunk has, each on its own \
line:
- IN: what arrives and its exact shape: the fields read, the type or format \
checked, conversions, and what happens to input that does not fit.
- ENTRY: each route, handler, listener, job or public function: who may call \
it and the checks that guard it, numbered in the order they run in the \
content (1., 2., ...), each as the code tests it - `if <condition as \
written> -> <result>` - never turned round into \
the condition that lets a call through, or "no check in this chunk". When the \
condition is a call's result, say what that result is (for example an error \
message, empty on success).
- RULE: each branch that changes the outcome, one per line - never several \
joined on one line: `if <exact condition> -> <outcome>`, with the function \
that holds it. Every early exit - a return, skip or raise that ends the work \
for some input - is a rule of its own. When a condition tests \
membership in a list, set, map or group, copy every member verbatim; never \
write "certain types" or "some statuses".
- LOOP: each loop that polls, retries or waits: how many times, the wait, and \
what ends it.
- ORDER: what is saved or committed, and in which order relative to calls \
that can fail (for example "commits status PAID, then publishes; a failed \
publish leaves it PAID").
- ON ERROR: each error handler: what it catches and what happens - \
re-raised, retried (how often), recorded (where), only logged, reported, or \
swallowed - and which later steps still run.
- CALLS OUT: each call to another service, queue, topic, email, file or \
table: the target as written (for an HTTP call, the method and the path after \
the base URL, and the variable that holds the base), the configuration key \
when the target comes from one, the credential sent, and the payload shape.
- STATES: each status or field value it sets or skips on, verbatim, with the \
branch that sets it.
- ABSENT: what the chunk plainly lacks where a reader would expect it (no \
permission check, no duplicate guard, no retry), as what this chunk shows, \
never as a claim about the system.
For documentation, configuration or other text, keep every decision, rule, \
value, step, name and reference to another document or system that a reader \
would look up, in the same spirit.

Absence is a fact too, in any kind of content: for each step that can fail, \
each case a rule might meet and each question a reader of this content would \
ask of it, when the chunk shows nothing that answers it - no handler around a \
call that can fail, no rule for a case, no owner of a step, no decision \
where one is due - write that on its own line, naming the step or case (for \
example "ABSENT: no handler around the profile update; an error goes to the \
caller", "ABSENT: no owner named for the approval step"). Silence is never \
left for a reader to read as "handled".

No word target: a chunk with one simple function needs three lines, a chunk \
with many branches needs all of them. Boilerplate (licence headers, imports, \
logging and server setup) collapses to one short line, or to nothing. Copy \
names, values and lists VERBATIM from the content - never infer or add ones \
that are not literally there, never guess about spelling, naming or intent. \
Write a constant, status or error code as the code writes it \
(`HTTPStatus.NOT_FOUND`, not a number it stands for). Never copy a password, \
token, key or a connection string that carries credentials; write <secret> in \
its place. Output only the condensation.

{content}"""

_BRIEF = """\
Below are the condensations of the sources of one topic of a larger system, \
each under its source's name. Write the brief of this topic. A reader (human \
or AI agent) gets only this brief - the condensations are not shown anywhere \
- so everything a reader needs to answer exact questions about this topic \
must be in it.

Open with a `# ` title saying what this topic holds, so it is told apart \
from other topics of the same service or system (for example "business-pay: \
build, deployment and tests" when it holds only those, not "business-pay"). \
Then write, in this order:
1. One or two sentences: what this topic does and what it hands work to or \
takes work from.
2. Contract: what reaches it and from where, what it sends or writes and to \
where, with the exact shape of messages or records that cross the boundary.
3. Entry points: for each route, handler, listener, job or public function, \
the checks that guard it in the order they run, each as the code tests it \
(`if <condition> -> <result>`), or that none is shown.
4. Decisions: every branch that changes an outcome, one line each - the \
exact condition, the outcome, and the function that holds it. Copy every \
member of a list, set or group verbatim. Include every state a record moves \
to and every check that refuses a caller. Where a condition names what it \
excludes (`not in`, `except`, `!=`), also name, from the states this topic \
or its connections use, which ones it lets through (`status not in \
[DONE, CANCELLED]` -> "so NEW and SEND_FAILED are picked up").
5. Order and failure: what is saved or committed before a step that can \
fail; for each step, how its failure is handled - what a handler catches, \
what happens, and which later steps still run - or that nothing handles it; \
each loop that polls or retries.
6. Connections: each other part of the system it calls, publishes to, \
consumes from, or shares a record or configuration key with - named as the \
condensations name it - and what crosses, in which direction.
7. Conclusions: what follows from the facts above that a reader would \
otherwise have to work out, each with the facts it rests on - what work a \
condition that drops or skips work drops, in concrete terms (which types, \
states or senders); where a part's name or stated purpose suggests a \
narrower or wider scope than its conditions, what it actually covers - both \
what it leaves out and what else it picks up; for a sweep, poll or \
scheduled re-send, which lost or stuck work of other parts it picks up - \
every case its condition matches, not only the one it is named for; what the \
same input arriving twice does; whether what each side of a connection \
sends - the live sender, never a test, fixture or script - matches \
what the other side accepts, and what happens to what does not (for example \
"it reads only a top-level `paymentToken`, which the current sender does not \
send, so it would skip every message that sender sends"); where no live \
sender or receiver was found, what that means for the work (nothing reaches \
this part today, or what it sends goes nowhere) and, when another part \
takes the same work, whether this part would accept what that part's sender \
sends; where another part does the same job (an old and a new path), each \
step one of them takes that the other lacks - a review, an authentication, \
a duplicate check - and what reaches the end without it; where a check that \
ends the work runs before an authentication or validation check, what gets \
through without that check; for a step nothing \
handles, which later steps a failure skips; what changing one part would and \
would not change elsewhere, including where another part keeps its own copy \
of a rule or record that a change to this one does not reach. Draw only what \
the facts support.
8. Hazards: where work can be lost, duplicated, corrupted or let through \
unchecked, as the condensations show it.
9. The sources to open first, and what each holds.
For documentation or other text, keep its decisions, rules, steps and \
references in the same spirit, under headings that fit it.

Say what the condensations show, never what a name suggests: when what a \
called job, endpoint or function does lives outside this topic, name it with \
what it is called with and mark it "(behaviour not in this topic)". Every \
check comes with its condition. Keep names, values and lists verbatim. No \
word target: one line per fact, no padding, no repetition. Leave out only \
startup and wiring, packaging, build and deployment files, logging setup, \
licences and test plumbing; name a test only when it pins down a decision. If \
the topic covers unrelated things, give each its own part. Write about the \
topic itself. Never describe the text you were given: no "this group", "this \
set", "these chunks", "the summaries", "condensed" or "the files above". \
Mention only what is actually present - do not invent anything.

Output only the description in markdown, nothing else.

{content}"""

_BRIEF_UPPER = """\
Below are descriptions of the parts of one area of a larger system, each \
under its title. Write what a reader (human or AI agent) must know about the \
whole area: what it does, and how work moves through its parts.

Open with one or two sentences: what this area does and what it hands work to \
or takes work from outside it. Then the end-to-end flows of the area - the \
things a user or another system asks of it - each as numbered steps from what \
starts it to what it ends with, naming at each step the part and the function \
that does it and the state the record moves to, and what happens when that \
step fails: what is left behind, and which part retries or repairs it, or \
that no part of this area does (a part elsewhere may). Give each step's \
failure as its part's description gives it: where steps fail differently \
(one catches its errors, the next lets them through and skips what follows), \
say so step by step, never as one rule for all; where a description does not \
say, write that. When a step drops or skips work without an error - a message \
it never processes, a record it ignores - the flow says so, with the kind of \
condition and the part that holds it, said as what the dropped work is (which \
types, which states), never only as the field its check reads. The last \
section, when there is one, lists parts outside this area that the parts \
here hand work to or take it from. Name such a part inside the step it \
acts on - never in a section of \
its own - and say it sits elsewhere: one that sends lost or stuck work round \
again is that step's repair (say which records it picks up), and one that \
consumes the same messages is a second path, whose own behaviour its \
description gives. A failure such a part repairs is never written as left \
for good. Where a part's description draws a conclusion that bears on a \
step - what a check drops, a mismatch with the part it talks to, which steps \
a failure skips - the step carries it. Then one line per part \
not already named in a flow, saying its job. End with the hazards that come \
from how the parts interact, in the same terms: what no part of this area \
repairs, never that nothing does.

Aim for 400 to 900 words, however many parts there are: every part's brief is \
in the map below this one, so a step names the part, what it does and what \
passes on, never the part's own checks, lists or fields - a reader opens the \
part for those. Leave out setup, configuration and style hazards. Name a part \
by its title so a reader can open it. Mention only what the descriptions say \
- do not invent anything. Write about the area itself. Never describe the \
text you were given: no "this group", "this set", "these chunks", "the \
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
