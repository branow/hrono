"""The leaf brief prompts under test, as data.

`today` is hrono's seeded default. The others describe the leaf as one part
of a system - what it is for, what crosses its boundary, the ideas it owns -
instead of describing the input ("this group of chunks"). None uses code
vocabulary: inputs, outputs, rules and flows describe any black box.
"""

from __future__ import annotations

from hrono.registry.collections.prompts import _BRIEF

_NO_META = """\
Write about the part itself. Never describe the text you were given: no \
"this group", "this set", "these chunks", "the summaries", "condensed" or \
"the files above"."""

_TAIL = """\
Say what things do, never only that they exist: a name without what it does \
is noise. Licences, server and logging setup, environment defaults and \
packaging get one line at most, and only if they matter to a reader. \
Mention only what is actually present - do not invent anything.

Output only the description in markdown, nothing else."""

_DECISIONS = """\
Below are notes on the sources of one part of a larger system, each under \
its source's name. Describe that part for a reader (human or AI agent) who \
must find where something happens and then change or rely on it.

Open with one or two sentences: what this part does and what larger thing \
it belongs to. Then, in whatever form serves this part:
- what reaches it and from where, and what it sends or writes and to where, \
with the message or record shapes that cross that boundary;
- every decision it makes: the condition, the outcome, and the identifier \
that holds the condition (a constant, list, field or function) - this is \
what a reader most often needs, so do not drop a decision to save words;
- the data it reads and writes, with the fields that matter;
- the main flows, step by step;
- the sources to open first, and what each holds.
Tests are evidence of expected behaviour: state the behaviour they pin \
down, do not describe the tests. If the notes cover unrelated things, say \
so and describe each on its own; do not force one story.
End with at most five hazards, only ones that change what a caller or \
changer gets: lost or partial work, silent failure, a wrong or surprising \
state. Skip naming, style, dead code and defaults.

Do not walk through the sources one by one. Spend words on decisions and \
hand-offs, not on setup."""

_CONTEXT = """\
For orientation only - other parts that sit near this one, by their \
sources (do not describe them; use them to name where this part's inputs \
come from and its outputs go, when the notes make that clear):
{context}"""

BRIEF = {
    "today": _BRIEF,
    "blackbox-sections": f"""\
Below are notes on the sources of one part of a larger system, each under \
its source's name. Describe that part as a black box: what a reader (human \
or AI agent) needs to use it, reason about it, or decide whether to open it.

Write these sections in this order. Leave a section out when there is \
nothing for it.

## Purpose
What this part is for and what it is responsible for, in 2-4 sentences.

## Inputs
What reaches it and from where: requests, calls, messages, events, \
schedules, data it reads.

## Outputs
What it produces and where it goes: results, data it writes, messages it \
emits, other parts it calls.

## Concepts and rules
The ideas this part owns, their states, and the rules that move between \
them. Each in one or two sentences saying what it means and what enforces \
it, naming the identifiers that implement it.

## Flows
The main sequences that run through this part, step by step, from what \
starts them to what they end with.

## Where to look
The 2-5 sources to open first, and what each one holds.

## Caution
What could hurt someone changing or relying on this part: behavior \
differing from what names suggest, silent no-ops, partial operations, \
fragile special cases. Not trivia.

{_NO_META} {_TAIL}

{{content}}""",
    "blackbox-free": f"""\
Below are notes on the sources of one part of a larger system, each under \
its source's name. Describe that part as a black box: what a reader (human \
or AI agent) needs to use it, reason about it, or decide whether to open it.

These are content requirements only; the form is free (headings, prose, \
lists or tables - whatever serves this part):
- what this part is for and what it is responsible for;
- what reaches it and from where, and what it produces and where that goes;
- the ideas it owns, their states and the rules that change them, each said \
in a sentence or two with the identifiers that implement it;
- the main sequences that run through it, step by step;
- which sources to open first;
- what could hurt someone changing or relying on it (not trivia).

Do not walk through the sources one by one. {_NO_META} {_TAIL}

{{content}}""",
    "purpose-budget": f"""\
Below are notes on the sources of one part of a larger system, each under \
its source's name. Describe that part for a reader (human or AI agent) who \
must decide whether to open it and then reason about it.

Open with one or two sentences: what this part does in the system, and for \
whom. Then cover, in whatever form serves this part best:
- what comes in and from where, and what goes out and to where;
- the ideas it owns: their states and the rules that change them, each said \
in a sentence or two with the identifiers that implement it;
- the main flows, step by step;
- the 2-5 sources to open first;
- what could hurt someone changing or relying on it (not trivia).

Do not walk through the sources one by one. Aim for 250 to 450 words; only \
a part with many distinct responsibilities may use more. {_NO_META} {_TAIL}

{{content}}""",
    "decisions": f"""\
{_DECISIONS} {_NO_META} {_TAIL}

{{content}}""",
    "decisions-tight": f"""\
{_DECISIONS} Aim for 400 to 700 words: keep every decision and hand-off, \
and cut setup, field lists and test detail first. {_NO_META} {_TAIL}

{{content}}""",
    "core": f"""\
Below are notes on the sources of one part of a larger system, each under \
its source's name. Write what a reader (human or AI agent) must know about \
this part to understand its role in the system and to find where to change \
it. The notes stay available below this description, so leave detail to \
them: keep what is fundamental, drop what is obvious or minor.

Keep, in this order:
1. One or two sentences: what this part does and what it hands work to or \
takes work from.
2. Its contract with the rest of the system: what reaches it and from \
where, what it sends or writes and to where, with the shape of messages or \
records that cross the boundary.
3. The decisions that shape its behaviour: the condition, the outcome, and \
the function, constant or list that holds it.
4. Hazards that lose, duplicate or corrupt work, or fail silently - at most \
three.
5. The two to four sources to open first, and what each holds.

Leave out: startup and wiring, configuration keys and defaults, lists of \
fields or enum values, health checks, version helpers, logging, test \
plumbing, and any hazard about style, naming or types. Name a test only \
when it pins down a behaviour from point 3. If the notes cover unrelated \
things, say so and give each its own short description.

Aim for 150 to 350 words. {_NO_META} {_TAIL}

{{content}}""",
    "core-states": f"""\
Below are notes on the sources of one part of a larger system, each under \
its source's name. Write what a reader (human or AI agent) must know about \
this part to understand its role in the system and to find where to change \
it. The notes stay available below this description, so leave detail to \
them: keep what is fundamental, drop what is obvious or minor.

Keep, in this order:
1. One or two sentences: what this part does and what it hands work to or \
takes work from.
2. Its contract with the rest of the system: what reaches it and from \
where, what it sends or writes and to where, with the shape of messages or \
records that cross the boundary.
3. The decisions that shape its behaviour, one line each: the condition, \
the outcome, and the function, constant or list that holds it. Include \
every step that moves a record from one state to another (created, \
submitted, paid, reviewed, resubmitted, completed, deleted - whatever this \
part has) and every check that refuses a caller (authorization, \
validation, locks), naming the function that does it.
4. Hazards that lose, duplicate or corrupt work, or fail silently - at most \
three.
5. The two to four sources to open first, and what each holds.

Leave out: startup and wiring, configuration keys and defaults, lists of \
fields or enum values, health checks, version helpers, logging, test \
plumbing, and any hazard about style, naming or types. Name a test only \
when it pins down a behaviour from point 3. If the notes cover unrelated \
things, say so and give each its own short description.

Write compactly: one line per decision, no padding. Aim for 250 to 500 \
words; a part with several distinct jobs may use up to 800. {_NO_META} {_TAIL}

{{content}}""",
    "core-scaled": f"""\
Below are notes on the sources of one part of a larger system, each under \
its source's name. Write what a reader (human or AI agent) must know about \
this part to understand its role in the system and to find where to change \
it. The notes stay available below this description, so leave detail to \
them: keep what is fundamental, drop what is obvious or minor.

Keep, in this order:
1. One or two sentences: what this part does and what it hands work to or \
takes work from.
2. Its contract with the rest of the system: what reaches it and from \
where, what it sends or writes and to where, with the shape of messages or \
records that cross the boundary.
3. The decisions that shape its behaviour: the condition, the outcome, and \
the function, constant or list that holds it.
4. Hazards that lose, duplicate or corrupt work, or fail silently - at most \
three per job. Not types, naming or style.
5. The two to four sources to open first, and what each holds.

Leave out: startup and wiring, configuration keys and defaults, lists of \
fields or enum values, health checks, version helpers, logging, test \
plumbing, and any hazard about style, naming or types. Name a test only \
when it pins down a behaviour from point 3. If the notes cover unrelated \
things, say so and give each its own short description.

Length follows the number of distinct jobs this part does, not the length \
of the notes: about 150 to 250 words for each job, with points 2 to 4 given \
per job when the jobs differ. A job is something a caller or another part \
asks of it (accept a payment, sync with another system, list pending \
work), not a source. {_NO_META} {_TAIL}

{{content}}""",
    "map": f"""\
Below are notes on the sources of one part of a larger system, each under \
its source's name. Describe that part for a reader (human or AI agent) who \
must find where something happens and then change or rely on it.

First, in one short paragraph: what this part does, what larger thing it \
belongs to, what reaches it and what it sends out. Then its main flows, \
step by step, naming each decision (condition, outcome, and the identifier \
that holds it). Then a map: one line per source that carries logic, saying \
what it decides or holds - group trivial sources (licences, setup, empty \
packages, test plumbing) into one line. Tests are evidence: state the \
behaviour they pin down. End with at most five hazards that change what a \
caller or changer gets; skip naming, style, dead code and defaults. \
{_NO_META} {_TAIL}

{{content}}""",
    "decisions-ctx": f"""\
{_DECISIONS} {_NO_META} {_TAIL}

{_CONTEXT}

{{content}}""",
}

# A second sample of a prompt: the same text plus a trailing newline, so it
# misses the cache. Measures how much one prompt's briefs vary run to run.
BRIEF["core#2"] = BRIEF["core"] + "\n"
BRIEF["core-states#2"] = BRIEF["core-states"] + "\n"
