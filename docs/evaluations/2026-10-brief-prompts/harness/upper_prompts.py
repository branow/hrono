"""The upper brief prompts under test, as data.

An upper brief is written from the briefs of the parts below it (here the
`core-states` leaf briefs), each under its title. `today` is hrono's seeded
default. The others carry the leaf pick's ideas one level up: say what the
area does and how its parts work together, keep what only shows when the
parts are seen together, and leave each part's detail to its own brief.
"""

from __future__ import annotations

from prompts import _NO_META

from hrono.registry.collections.prompts import _BRIEF_UPPER

_KEEP = """\
Leave out what one part's description already says in detail - a reader \
opens that part for it - and setup, configuration, field lists and style \
hazards. Name a part by its title so a reader can open it. Mention only \
what the descriptions say - do not invent anything. {no_meta} Output only \
the description in markdown, nothing else."""

UPPER = {
    "today": _BRIEF_UPPER,
    "area-core": f"""\
Below are descriptions of the parts of one area of a larger system, each \
under its title. Write what a reader (human or AI agent) must know about \
the whole area to understand its role in the system and to choose which \
part to open.

Keep, in order:
1. One or two sentences: what this area does and what it hands work to or \
takes work from outside it.
2. Its parts, one line each: the part's title and the job it does in the \
area.
3. How the parts work together: each flow that crosses parts, step by step, \
naming at each step the part and the function that does it; and each \
record whose states are changed by more than one part, with which part \
moves it to which state.
4. Rules and conventions shared by several parts.
5. At most three hazards that come from how parts interact (one part \
assuming what another does) or that lose or corrupt work.

Aim for 300 to 600 words, however many parts there are. \
{_KEEP.format(no_meta=_NO_META)}

{{content}}""",
    "area-flows": f"""\
Below are descriptions of the parts of one area of a larger system, each \
under its title. Write what a reader (human or AI agent) must know about \
the whole area: what it does, and how work moves through its parts.

Open with one or two sentences: what this area does and what it hands work \
to or takes work from outside it. Then the end-to-end flows of the area - \
the things a user or another system asks of it - each as numbered steps \
from what starts it to what it ends with, naming at each step the part and \
the function that does it and the state the record moves to. Then one line \
per part not already named in a flow, saying its job. End with at most \
three hazards that come from how the parts interact.

Aim for 300 to 600 words, however many parts there are. \
{_KEEP.format(no_meta=_NO_META)}

{{content}}""",
    "area-map": f"""\
Below are descriptions of the parts of one area of a larger system, each \
under its title. Write a guide to the area for a reader (human or AI agent) \
who has a question and must pick the part that answers it.

Open with one or two sentences: what this area does and what it hands work \
to or takes work from outside it. Then, for each part, one or two lines: \
its title, its job, and the questions it answers (for example "how a \
filing is paid", "who may delete a draft"). Then, briefly, the flows that \
cross parts, as a chain of part titles with what passes between them.

Aim for 200 to 450 words, however many parts there are. \
{_KEEP.format(no_meta=_NO_META)}

{{content}}""",
}
