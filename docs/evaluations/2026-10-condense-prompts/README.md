# Condense prompts: does a condensation say what a chunk is for?

Pilot, 2026-10-11, on 9 sections of the `bcreg` corpus. 45 Haiku calls
(5 new prompts × 9 sections); today's condensations are the ones stored in
the tree. It follows `../2026-10-cluster-formula/`, which found that a
section clusters with whatever its text opens with, and that today's
condensations often open with a licence or a mechanism ("NATS queue
handler") instead of the job the code does.

## Sections

- The E23 payment listener `entity_pay/worker.py`, two files of its flow
  (`business_pay/resources/pay_filer.py`, `file_future_effective.py`) and
  the three test files it was clustered with (`test_nats_stan.py`,
  `test_queue_publish.py`, both sections of `conftest.py`).
- A configuration file (`entity_pay/config.py`) and a markdown document
  (`sbc-pay/docs/.../FAS_Intgeration.md`), to see the prompts on non-code.

## Prompts

In `harness/prompts.py`:

- `today`: hrono's seeded condense prompt.
- `behaviour`: purpose, what comes in, what goes out, rules, as a list.
- `purpose-first`: one opening sentence on the job it does and for whom, in
  the system's terms; then inputs, outputs, rules and flow; mechanism after.
- `what-how`: the same content in a fixed `WHAT:` / `HOW:` shape.
- `purpose-lean`: `purpose-first`, told to drop detail a reader gets by
  opening the source (log calls, message texts, timings, wiring).
- `purpose-budget`: `purpose-first` plus "aim for 60 to 120 words; only
  dense logic may use more".

## Results

| prompt | words per section | opens with a licence | unsupported identifiers (9 sections) | listener nearer its flow than a test (granite) |
|---|---|---|---|---|
| `today` | 89 | 5 of 9 | 3 | 100% (margin +0.061) |
| `behaviour` | 174 | 0 | 5 | 100% (+0.070) |
| `purpose-first` | 170 | 0 | 4 | 100% (+0.080) |
| `what-how` | 165 | 0 | 2 | 100% (+0.076) |
| `purpose-lean` | 175 | 0 | 4 | 100% (+0.080) |
| `purpose-budget` | 105 | 0 | 3 | 100% (+0.093) |

"Unsupported identifiers" is hrono's mechanical faithfulness check: names in
the condensation that do not appear in the source. With granite embeddings
every prompt already keeps the listener with its flow, so the margins differ
little; this pilot is too small to rank prompts by clustering.

How each one opens, for the listener (all 9 sections, all prompts, in full:
[data/outputs.md](data/outputs.md)):

| prompt | opening |
|---|---|
| `today` | NATS payment queue handler. Flow: extract payment token JSON → validate … |
| `behaviour` | **Purpose:** NATS Streaming worker that processes payment notifications and advances filings … |
| `purpose-first` | Processes payment completion messages from NATS Streaming queue and applies confirmed payments to their business filings; publishes filing for processing and notification email when ready. |
| `what-how` | WHAT: Worker for the entity-pay service that processes payment tokens from a NATS Streaming queue and updates filing statuses accordingly … |

And for the future-effective job:

| prompt | opening |
|---|---|
| `today` | **Future Effective Date Service**: Flask + asyncio worker that polls legal-api … |
| `purpose-first` | Picks up filings marked for future effective dates from the legal API and places them on the entity filer queue for processing. |

## Reading

- `today` opens 5 of 9 sections with the licence ("BSD 3-Clause
  License …"), and code sections with their framework. Both are what made
  unrelated files look alike.
- `purpose-first` (and `purpose-budget`) opens every section with the job it does, in the domain's
  words ("applies confirmed payments to their business filings"). Tests and
  configuration say what they are first ("Integration test suite for …",
  "Configuration for the entity-pay service …").
- `what-how` has the same content and the fewest unsupported names, but
  every condensation starts with the same token `WHAT:`, and its opening
  for the listener drifts back to the mechanism ("Worker … from a NATS
  Streaming queue").
- `behaviour` opens with a `**Purpose:**` header and is the least faithful
  (5 unsupported names).
- `purpose-budget` keeps the purpose-first opening at 105 words a
  section, close to today's 89, and keeps the GOTCHA lines. The budget
  held, unlike the earlier research finding that budgets are ignored
  (there the budget was a hard size; here it is a range with an escape
  for dense logic). It sometimes adds context the chunk does not state
  ("in a BC business registry").
- `purpose-lean` did not get shorter: told what to drop, Haiku kept it.
- The other new prompts write about twice as much (about 170 words against
  89). Condense output tokens and brief input double with them.

## The unsupported names, checked by hand

| prompt | file | flagged | in the source |
|---|---|---|---|
| all but `today` | `pay_filer.py` | `403`, `404` | `HTTPStatus.FORBIDDEN`, `HTTPStatus.NOT_FOUND`: a translation, true |
| `purpose-first` | `pay_filer.py` | `corpTypeCode`, `filingIdentifier`, `statusCode` | the event's camelCase keys, which the code converts to `corp_type_code` and so on: inferred, true |
| `behaviour`, `what-how` | `pay_filer.py` | `camelCase` | an ordinary word, not a name |
| `today`, `behaviour` | `pay_filer.py` | `corp_types`, `corp_type_codes` | not in the source: invented names |
| `today` | `conftest.py` | `async_coro_fn` | not in the source |
| `behaviour` | `config.py` | `entity_pay` | the source has `entity-pay` |

None of the new prompts' flags is an invented name except `behaviour`'s
`corp_type_codes`. The check counts translations and inferred keys too, so
its number alone does not rank prompts.

## "This group is …" openings are a brief problem

Pilot outputs open with the content itself: no condensation in this pilot
starts with "This is …" or "Here is …". In the stored tree, 66 of 8,281
condensations do, all of them notes on binary or encoded data. The briefs
are where it happens:

| level | briefs | open with "This group / set / These …" | mention condensations, summaries, chunks or fragments in the first 300 characters |
|---|---|---|---|
| leaves | 536 | 381 (71%) | 481 (90%) |
| level 1 | 25 | 0 | 19 |

Today's brief prompt asks for it: "Start by stating what this group is as a
whole", over input it calls "content chunks". That is the brief prompt's
fix, not condense's.

## Superseded by `purpose-decisions`

The brief experiment (`../2026-10-brief-prompts/`, round 2) scored briefs
against verified facts and found condense was their limit: the
`purpose-budget` condensation of business-pay's `pay_filer.py` dropped
`create_staff_review`, the hard-coded review list and the fields it reads,
so no brief could state them, and its speculative GOTCHA ("`NATS_FILER_SUBJECT`
may be misspelled") reached every brief. `purpose-decisions` keeps the
purpose-first opening and adds: every decision with the function, constant,
list or field that holds it; up to 250 words for a chunk with many
decisions; a GOTCHA only for what the code shows, never a guess about
spelling, naming or intent. It is the prompt the rebuild uses.

## Next (as first written)

`purpose-budget` is the candidate. Before it replaces the default it needs
the run the formula was chosen on: condense the whole corpus with it, embed
with granite, cluster with the chosen formula, and check the E23 trace and
the scores of `../2026-10-cluster-formula/`. That is about 8,500 Haiku
calls, so it waits for a decision.

## Reproduce

```
cd harness
uv run python pilot.py ~/hrono-eval/db/hrono.db ../data $CACHE [prompt ...]
```
