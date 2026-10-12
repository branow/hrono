"""The condense prompts under test, as data.

`today` is hrono's seeded default, imported so it cannot drift from what the
tree was built with. The others put what a chunk is FOR before how it is
built: the embedding model weighs the start of a text most, and a chunk that
opens with its mechanism ("NATS queue handler") lands with other chunks of
that mechanism instead of with its feature.
"""

from __future__ import annotations

from hrono.registry.collections.prompts import _CONDENSE

_FAITHFUL = """\
Copy names and values VERBATIM from the content - never infer or add ones \
that are not literally there. If the content holds anything non-obvious a \
newcomer could be hurt by (behavior differing from what names suggest, \
silent no-ops, partial or non-transactional operations, asymmetries, \
workarounds, fragile special cases), add a line starting with 'GOTCHA:' for \
each - only if literally present. Output only the condensed content."""

_FAITHFUL_SHOWN = """\
Copy names and values VERBATIM from the content - never infer or add ones \
that are not literally there. If the code itself shows something a newcomer \
could be hurt by (an exception swallowed, a partial or non-transactional \
update, a hard-coded special case, behaviour differing from what a name \
says), add a line starting with 'GOTCHA:' for each. Never guess about \
spelling, naming or intent. Output only the condensed content."""

PROMPTS = {
    "today": _CONDENSE,
    "behaviour": f"""\
Condense this content chunk for a reader who needs to know what it DOES, \
not what it contains. State:
- its purpose: what this part is for;
- what comes in: requests, calls, messages, events, triggers, data it reads;
- what goes out: results, data it writes, messages it emits, other parts it \
calls;
- the rules and states it enforces or changes, as plain statements.
Name an identifier only together with what it does or means - never as a \
bare list of names. Boilerplate (licence headers, imports, generated code, \
plain configuration, repetitive declarations) collapses to one short line, \
or to nothing if it says nothing about behaviour. Let the length follow how \
much behaviour there is. {_FAITHFUL}

{{content}}""",
    "purpose-first": f"""\
Condense this content chunk. Start with one sentence saying what it is for, \
in the terms of the system it belongs to: the job it does and for whom (for \
example "Applies a confirmed payment to its business filing"), not how it \
is built. If it is a test, fixture, configuration, build file, migration or \
documentation, say so in that first sentence and name what it serves.

Then give what a reader needs to rely on it: what comes in, what goes out, \
the rules and states it enforces, and the steps of its main flow. Name \
identifiers together with what they do, never as bare lists. Mechanism \
(frameworks, queues, retries, wiring) comes after the purpose. Boilerplate \
(licence headers, imports, logging and server setup, plain configuration) \
collapses to one short line, or to nothing. Let the length follow how much \
behaviour there is. {_FAITHFUL}

{{content}}""",
    "what-how": f"""\
Condense this content chunk in exactly this shape:

WHAT: one sentence - what it is for, in the terms of the system it belongs \
to: the job it does and for whom, not how it is built. If it is a test, \
fixture, configuration, build file, migration or documentation, say so and \
name what it serves.
HOW: what comes in, what goes out, the rules and states it enforces, and \
the steps of its main flow. Name identifiers together with what they do, \
never as bare lists. Mechanism after behaviour. Boilerplate (licence \
headers, imports, logging and server setup, plain configuration) gets one \
short line, or nothing.

Let the length of HOW follow how much behaviour there is. {_FAITHFUL}

{{content}}""",
    "purpose-lean": f"""\
Condense this content chunk. Open with one sentence: what it is for, in the \
terms of the system it belongs to - the job it does and for whom, not how it \
is built. A test, fixture, configuration, build file, migration or document \
says so in that sentence and names what it serves.

Then keep only what a reader needs to find this part and reason about it: \
what comes in, what goes out, the rules and states it enforces, the steps of \
its main flow. Name identifiers together with what they do. Drop \
line-by-line detail a reader would get by opening the source: log calls, \
message texts, sleep and retry timings, framework wiring, boilerplate. \
{_FAITHFUL}

{{content}}""",
    "purpose-budget": f"""\
Condense this content chunk. Start with one sentence saying what it is for, \
in the terms of the system it belongs to: the job it does and for whom (for \
example "Applies a confirmed payment to its business filing"), not how it \
is built. If it is a test, fixture, configuration, build file, migration or \
documentation, say so in that first sentence and name what it serves.

Then give what a reader needs to rely on it: what comes in, what goes out, \
the rules and states it enforces, and the steps of its main flow. Name \
identifiers together with what they do, never as bare lists. Mechanism \
(frameworks, queues, retries, wiring) comes after the purpose. Boilerplate \
(licence headers, imports, logging and server setup, plain configuration) \
collapses to one short line, or to nothing. Aim for 60 to 120 words; only \
dense logic may use more. {_FAITHFUL}

{{content}}""",
    "purpose-decisions": f"""\
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
after the purpose. Boilerplate (licence headers, imports, logging and \
server setup, plain configuration) collapses to one short line, or to \
nothing. Aim for 60 to 120 words; a chunk with many decisions may use up to \
250. {_FAITHFUL_SHOWN}

{{content}}""",
    "contracts": f"""\
Condense this content chunk. Start with one sentence saying what it is for, \
in the terms of the system it belongs to: the job it does (for example \
"Applies a confirmed payment to its business filing"), not how it is built. \
If it is a test, fixture, configuration, build file, migration or \
documentation, say so in that first sentence and name what it serves.

Then give what a reader needs to find and change its behaviour: what comes \
in, what goes out and in what shape, the steps of its main flow, and every \
decision it makes - the condition, the outcome, and the function, constant, \
list or field that holds it. For every entry point (route, handler, \
listener, job, public method) say who may call it and the check that \
enforces it, with the exact condition - or, when the chunk shows none, \
say "this chunk shows no check" (a caller elsewhere may check; never claim \
more than the chunk shows). For every call out of it (another service, a queue, an email, a \
database write) give the target, the credentials it sends and the payload \
shape. Say what is saved before a later step can fail, and whether a \
failure is recorded, retried, re-raised or only logged. State what the code \
plainly lacks when it matters: no permission check, no duplicate guard, no \
retry, a check that is commented out - each as what this chunk shows. For \
a test, say what behaviour it \
asserts and that it is a test. Name identifiers together with what they \
do, never as bare lists. Boilerplate collapses to one short line, or to \
nothing. Aim for 60 to 150 words; a chunk with many entry points or \
decisions may use up to 300. {_FAITHFUL_SHOWN}

{{content}}""",
}
