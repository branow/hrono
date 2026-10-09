# PO note 2026-09-12 — the four product calls from the e2e QA run

Raised by the end-to-end run of 2026-09-03 (`.e2e/RUN-LOG.md`,
`.e2e/FINDINGS.md`). Tickets 092-108 carry every technical fix; the dev role
decided those directly. These four are NOT technical calls — each changes what
hrono is, not how it is built. Each blocks part of a ticket, noted below.

---

## A. WITHDRAWN 2026-09-12 — not a product call

Raised as "what should a small corpus produce?". PO review: the root is not a
special thing, it is just the one node left at the top, and `_collect_root`
already implements exactly that — "if recursion stopped with >1 top node, parent
them all under a single root and brief it". 7 topics simply get one parent.

The real defect is that clustering parameters are not scaled per level, which
the spec already requires (`how-hrono-works.md:109`) — folded into **094**.
Export's forest handling folded into **096**: a forest is a defect to fail on,
not a shape to render.

## B. DECIDED 2026-09-14

Ignore by default (opt-in to include): assets (`.svg .eps .ico .map .min.js
.min.css`, fonts), tabular data (`.csv .tsv`), generated code (`*_pb2.py`,
`*.pb.go`, `*.g.dart`, `*.generated.*`, OpenAPI clients), vendored trees
(`vendor/`, `third_party/`). Recorded in **104**.
Bad-brief handling: retry once, then store-and-flag, never drop the node.
Recorded in **103**.

## C. DECIDED 2026-09-21 — recorded in full on #126, which is now unblocked

Ruled after #127 and #134 changed the evidence: a RESERVE (no document takes
more than 40% of the window while another has a qualifying hit unplaced),
not the recommended hard cap of 2 — concentration now tracks the question
rather than a defect. Brief and source capped together with no reserved slot
(#134: a brief cleared the floor for 1 of 22 questions; why is #135). A
window that cannot be filled from distinct documents returns FEWER hits and
never pads. The off-topic gate stands as ruled at #127's close.

Original question, for the record:

### C (as raised). How should a recall result window be composed?

Measured on the QA corpus:

```
"how do I set the color level in chalk"     limit=10 -> 10 hits from 4 documents
"how does the signer verify a signature"    limit=10 -> 10 hits from 2 documents
```

Nothing diversifies by source document, so one file can own the whole window.
Three decisions:

1. **Diversity**: a hard per-document cap (e.g. max 2 passages per document),
   MMR-style re-ranking, or nothing (accept that a focused question deserves a
   focused answer).
2. **Brief vs source mix**: should a result set be allowed to be all summaries,
   all source, or should it deliberately mix — e.g. "the topic brief plus the
   best source passages under it"? Today it is whatever scores.
3. **Off-topic gate**: two of five nonsense questions still returned hits
   ("quantum entanglement in banana futures" -> 1, "the mitochondria..." -> 3).
   Is a weak-but-nonzero answer better than "explore the map", or is a false
   answer worse than none? That is a product stance, not a threshold.

## D. DECIDED 2026-09-21 — one command; #106 split into 137/138/139

Decided with the product owner. Answers to the four questions as raised:

1. **ONE operator verb.** `hrono tree sync <name>` runs the whole chain, in
   order, as one op. `maintain` is kept for the COLD build only.
   **Corrected 2026-09-21 at #137's close — the chain order below and in the
   original note was WRONG.** It read
   `... -> condense -> brief -> propagate -> monitor -> repair`; in that order
   `propagate` selects nothing, because it judges a leaf's new content against
   its STORED brief and briefing first overwrites that brief with the current
   signature. No ancestor is ever marked and the upper levels silently keep
   describing content that changed underneath them. The correct order is
   `update -> propagate -> brief -> brief-upper -> monitor -> repair`.
2. **Individual ops are a debug surface, not a product surface.** A generic
   admin-only `POST /jobs {op, scope}` exists so a stuck tree can be poked at;
   there is deliberately no per-op CLI command. The September run had to insert
   job rows by hand, which is the evidence that the escape hatch is needed; it
   is not evidence that it should be pretty.
3. **hrono never acts on its own.** Nothing runs on a timer. `monitor` runs
   inside the chain because it is cheap (0.0 s over 92 members); `settle` is
   expensive and stays explicitly invoked — its churn trigger INFORMS, it does
   not fire. No unattended LLM spend, ever.
4. **The same verbs serve both.** The CLI is already a thin client of the API
   (`serve` owns the database, everything else is HTTP), so there is one surface
   and the M10 dashboard is a third client of it. No separate agent-facing API.

**Why one verb and not eight.** The steps are order-coupled and the coupling is
not obvious: #122 was exactly the bug where the chain skipped a step, and the
result was briefs citing sources they had never read — a map that looks right
and is quietly wrong, with no error anywhere. A single verb cannot be sequenced
incorrectly. That is worth more than the flexibility of per-step commands, which
almost no user wants and every user can get wrong.

Original question, for the record:

### D (as raised). What is the operator-facing workflow?

`maintain` is the only thing anyone can trigger. `update`, `propagate`,
`monitor`, `repair`, `settle` are implemented, tested, and unreachable — the QA
run had to write job rows directly, then drive ops in-process.

The gap is not just missing endpoints, it is a missing chain. `update` re-places
changed chunks but never condenses them: after the QA scenarios, 3 member
sections had no condensation, so `propagate` judged a topic against an
incomplete source. Something has to own "bring this tree up to date", and what
it runs is a design decision:

```
sync -> diff -> reconcile -> embed -> place -> condense(changed) ->
brief(stale) -> propagate -> monitor -> repair -> [settle if triggered]
```

Decisions needed:

1. Is there ONE operator verb (`hrono tree sync <name>` / `POST .../update`)
   that runs that whole chain, with `maintain` kept only for a cold build?
2. Should the individual ops be triggerable at all, or is that a debug surface?
   (A generic `POST /jobs {op, scope}` is the cheap answer; a curated set of
   verbs is the honest one.)
3. What runs automatically? `monitor` after every update is cheap (it was 0.0 s
   on 92 members). `settle` is expensive and already gated by its own trigger.
   Does hrono ever act on its own, or does an operator always ask?
4. Which of this is the agent-facing API vs the human-facing CLI? The dashboard
   (M10) will want the same verbs.
