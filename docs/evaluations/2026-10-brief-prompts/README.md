# Brief prompts: does a leaf brief explain the part it covers?

Pilot, 2026-10-11, on one leaf of `bcreg`: leaf 378 of the chosen
clustering (`../2026-10-cluster-formula/`, `cond6-h4+g`, seed 42), the
business-pay queue service. 22 sections in 22 files, including its
`LICENSE`, config, `wsgi.py` and a few tests. 26 model calls: 22 Haiku
condensations with the chosen condense prompt (`purpose-budget`,
`../2026-10-condense-prompts/`) and 4 Sonnet briefs.

## What is wrong with today's briefs

Measured on the 564 briefs of the stored `bcreg` tree:

- 71% of leaf briefs open by describing their input ("This group is …",
  "This set is …"), and 90% mention condensations, summaries, chunks or
  fragments near the start. The prompt asks for it: "Start by stating what
  this group is as a whole", over input it calls "content chunks".
- Upper briefs run longer than the leaves below them (median 1,177 words
  against 629).
- Leaf briefs are catalogs. The stored brief of the business-pay leaf
  opens with a licence paragraph, is organised by technical layer
  (bootstrap and config, data model, messaging, utilities) and gives the
  one thing the service does a single bullet among gunicorn and WSGI
  settings. The prompt's "one section per grouping" leads there.

## Prompts

In `harness/prompts.py`. All but `today` tell the model to write about the
part itself and never about its input, and to give licences, server setup
and environment defaults one line at most.

- `today`: hrono's seeded brief prompt.
- `blackbox-sections`: fixed sections: Purpose, Inputs, Outputs, Concepts
  and rules, Flows, Where to look, Caution.
- `blackbox-free`: the same requirements, free form.
- `purpose-budget`: one or two opening sentences on what the part does
  and for whom, the same requirements, and "aim for 250 to 450 words".

## Results

| prompt | words | opens by describing its input | boilerplate lines | unsupported names |
|---|---|---|---|---|
| `today` | 744 | no | 7 | 0 |
| `blackbox-sections` | 779 | no | 6 | 0 |
| `blackbox-free` | 848 | no | 4 | 0 |
| `purpose-budget` | 517 | no | 2 | 0 |

The briefs in full: [data/leaf-378/briefs.md](data/leaf-378/briefs.md);
their input: [data/leaf-378/input.md](data/leaf-378/input.md).

## Reading

- **The new condensations fix the openings on their own.** Even `today`
  now opens with what the service does ("applies payment-completion events
  to business Filings"), with no "This group is" and no licence
  paragraph. The input no longer starts with licences, so the brief does
  not either.
- **`today` is still a catalog.** It walks the files one by one under
  layer headings (`__init__.py`, `config.py`, `wsgi.py`, `utils.py`, …) and
  describes each test.
- **`blackbox-free` explains the service best.** Its main flow is 9
  numbered steps, from JWT check to routing to the email queue, and it says
  why a missing filing returns 404 (the filing row may not be committed
  yet). It is also the longest.
- **`blackbox-sections` spreads one idea over sections.** Its Inputs list
  every environment variable, and its Concepts section is mostly enum
  listings.
- **`purpose-budget` is the shortest and keeps the essentials:** inputs and
  outputs, routing after payment, ack semantics, a 4-step flow, the files to
  open first. Its "for whom" produced filler ("meant for people operating
  or changing the filings pipeline").
- **Every prompt's caution list is too long and mostly trivia**: a trailing
  comma in a default, unused `**kwargs`, a `utils.py` next to a `utils/`
  package. "Not trivia" in the prompt did not stop it.
- **A false gotcha travelled up from condense.** The condensation of
  `services/queue.py` says "`NATS_FILER_SUBJECT` config key may be
  misspelled (FILTER?)"; FILER is right (the entity-filer service). All
  four briefs repeat it. The condense prompt's GOTCHA rule invites
  speculation.

## Round 2: scored against verified facts

Reading briefs ranks them by how they read, not by what they carry. The
agents evaluation (`../2026-10-bc-registries-agents/data/arch.json`) has
verified facts about how the system works, each citing its files.
`harness/judge.py` takes the facts that cite a leaf's files, and a Sonnet
judge says for each whether the brief conveys what this part does in it (2
stated, 1 partly, 0 absent). Each brief is judged twice; the score is the
mean, and the condensations the brief was written from are judged too, as
the ceiling. Four leaves: 378 (business-pay, 12 facts), 264 (pay-api
models, 9), 275 (entity-filer processors, 14), 291 (legal-api filing
resources, 37).

**Condense is the first limit.** On leaf 378, with `purpose-budget`
condensations, today's prompt kept the most facts (0.81) and the shorter
prompts the fewest, but the input itself scored only 0.75: the
condensation of `pay_filer.py` drops `create_staff_review`, the
hard-coded review list and the fields it reads. A new condense prompt,
`purpose-decisions` (`../2026-10-condense-prompts/harness/prompts.py`),
asks for every decision with the function, constant, list or field that
holds it, allows up to 250 words for dense chunks, and allows a GOTCHA
only for what the code shows ("never guess about spelling, naming or
intent"). It removed the false `NATS_FILER_SUBJECT` gotcha and kept the
event type, the review list and the Completing Party lookup.

New brief prompts (in `harness/prompts.py`):

- `decisions`: what reaches it and what it sends, with the shapes; every
  decision with the identifier that holds it ("do not drop a decision to
  save words"); data read and written; flows; sources to open; tests as
  evidence of behaviour; unrelated content described apart; at most five
  hazards that change what a caller gets.
- `decisions-tight`: the same, "aim for 400 to 700 words".
- `decisions-ctx`: `decisions` plus the other leaves of its group, by
  folder and file names, to name where inputs come from and outputs go.
- `map`: summary and flows, then one line per source with logic.

With `purpose-decisions` condensations (facts conveyed, weighted by facts
per leaf; words are the mean brief length; the input averages 2,513
words):

| prompt | 378 | 264 | 275 | 291 | all 72 facts | words |
|---|---|---|---|---|---|---|
| `today` | 0.69 | 0.55 | 0.39 | 0.37 | 0.45 | 934 |
| `purpose-budget` | 0.75 | 0.50 | 0.52 | 0.30 | 0.44 | 582 |
| `decisions` | 0.85 | 0.55 | 0.54 | 0.53 | **0.59** | 1,514 |
| `decisions-tight` | 0.79 | 0.42 | 0.50 | 0.46 | 0.52 | 1,029 |
| `decisions-ctx` | 0.79 | 0.44 | 0.54 | 0.55 | 0.57 | 1,347 |
| (input) | 0.67 | 0.67 | 0.60 | 0.61 | 0.63 | 2,513 |

Per leaf and per fact: `data/condense-decisions/leaf-*/judge.md`; the
briefs: `briefs.md` beside it.

- `decisions` carries 94% of what its input carries, at 60% of its
  length. It is the only prompt that holds up on the big legal-api leaf
  (0.53 against 0.37).
- `purpose-budget` is short because it drops facts; on the leaf with the
  most facts it is the worst.
- The word cap is half obeyed (1,029 words against "400 to 700") and costs
  7 points.
- The neighbour list does not help: the judge sees no more hand-offs, and
  it names fewer of the cited files on leaf 291.
- No brief contradicted a fact. The judge's two runs differ by up to 0.25
  on one leaf; the gaps between prompts over 72 facts are larger than
  that, the gaps on one leaf are not.

## Round 3: keep what is fundamental, not every fact

The fact score only counts facts the agents evaluation asked about, which
are all important, so it never penalises filler: `decisions` won while half
of its words were field lists, startup steps and test plumbing. `core`
lists what to keep, in order (role, contract with the rest of the system,
the decisions that shape behaviour, at most three hazards that lose or
corrupt work, two to four sources to open), lists what to leave out
(startup, configuration, field and enum lists, health checks, versions,
logging, test plumbing, style hazards), says the notes stay available
below, and aims for 150 to 350 words. A second judge pass labels each line
of a brief "core" or "detail"; "detail share" is the share of the words
on detail lines.

| prompt | facts conveyed (72) | words | detail share | core words |
|---|---|---|---|---|
| `today` | 0.45 | 934 | 0.32 | about 635 |
| `decisions` | **0.59** | 1,514 | 0.41 | about 890 |
| `core` | 0.44 | **400** | **0.08** | about 370 |

Per leaf, facts conveyed and words for `core`: 378 0.75 (359), 264 0.45
(375), 275 0.50 (419), 291 0.32 (445).

- `core` carries what `today` carries in 43% of the words, and almost
  none of them are detail. On business-pay it keeps the contract, every
  decision, the stuck-PAID hazard and the files to open, in 359 words.
- It loses on the big legal-api leaf (291: 0.32 against 0.53 for
  `decisions`). That leaf holds v1 and v2 filing resources, tasks,
  documents, COLIN sync and credentials; 445 words cannot cover it, and the
  dropped facts (the authorization check on submission, bootstrap
  deregistration on delete) are not trivia. A fixed budget fits a leaf with
  one job, not a leaf with six.
- One style hazard still got through (`NATS_CONNECT_ERROR_COUNT_MAX` as a
  string).

## Round 4: states and refusals, run twice, checked on unseen leaves

**Run-to-run noise.** The same prompt sampled twice (`core` and `core#2`)
moves up to 0.17 on one leaf (378: 0.75 and 0.58) but its 72-fact total
barely moves (0.44 and 0.45). Differences under about 0.05 in the total
are noise; one leaf ranks nothing. From here every new prompt is sampled
twice.

- `core-scaled` (`core` with "150 to 250 words per distinct job"): 0.41,
  no better than `core`. On legal-api it organised by job and still
  dropped the review lifecycle.
- `core-states` (`core`, plus: "include every step that moves a record
  from one state to another and every check that refuses a caller,
  naming the function that does it"; "one line per decision"; "250 to
  500 words, up to 800 for several jobs"): legal-api from 0.32 to 0.46,
  the 72-fact total from 0.45 to 0.53, at about 650 words. Both samples
  agree.

**Unseen leaves.** Two leaves no prompt was tuned on: 277 (pay-api payment
models, 21 facts) and 351 (auth-api bootstrap and resources, 24 facts).
Their facts are mostly about files elsewhere, so even the input scores only
0.26 and 0.30; they check the ranking, not the level.

| prompt | 277 | 351 |
|---|---|---|
| `today` | 0.21 | 0.20 |
| `decisions` | 0.17 | 0.23 |
| `core` | 0.14 | 0.21 |
| `core-states` (2 samples) | 0.20 | 0.23 |
| (input) | 0.26 | 0.30 |

**All six leaves, 117 facts** (two-sample means where there are two):

| prompt | facts conveyed | words | detail share |
|---|---|---|---|
| `today` | 0.36 | 953 | 0.38 |
| `decisions` | **0.44** | 1,441 | 0.42 |
| `core` | 0.34 | **385** | **0.13** |
| `core-states` | 0.41 | 629 | 0.28 |
| (input) | 0.49 | 2,616 | |

`core-states` is the pick: within 0.03 of `decisions` at 44% of its words,
above `today` at two thirds of its length, with less detail than either.
Its business-pay brief: `data/condense-decisions/leaf-378/briefs.md`.

**What a prompt can no longer fix.**

- The input is the ceiling (0.49): what condense drops, no brief
  recovers. The next gains are in condense.
- The facts missed by every prompt are hand-offs to other parts
  (entity-filer, auth, the queue consumers). A leaf sees only its own
  sources; naming its neighbours by file did not help (`decisions-ctx`).
  That belongs to the upper brief or to links between parts.
- Wording changes now move the total by less than the noise; finding a
  better leaf prompt would take many more samples per prompt.

## Upper brief

`harness/upper.py` briefs every leaf of one level-1 group with
`purpose-decisions` + `core-states`, then writes the group's upper brief
from those leaf briefs, as hrono feeds them (each under `=== title ===`).
Every upper prompt is sampled twice; facts are those citing the group's
files, and "spanning" facts are those whose files sit in two or more of
its leaves: what only an upper brief can tell. Prompts in
`harness/upper_prompts.py`:

- `today`: hrono's seeded upper prompt.
- `area-core`: the leaf pick one level up: the area's role, one line per
  part, the flows that cross parts with the part and function at each
  step, records whose states several parts change, shared rules, hazards
  from interaction.
- `area-flows`: the area's role, then its end-to-end flows as numbered
  steps naming the part, the function and the state at each, then one line
  per part not in a flow, then hazards from interaction.
- `area-map`: a router: per part, its job and the questions it answers.

All aim for 300 to 600 words "however many parts there are" (`area-map`
200 to 450).

Group 13 (legal-api, 10 leaves; 69 facts, 53 spanning):

| prompt | words | facts conveyed | spanning facts | detail share |
|---|---|---|---|---|
| `today` | 514 | 0.19 | 0.23 | 0.23 |
| `area-core` | 654 | 0.35 | 0.40 | 0.30 |
| `area-flows` | 726 | 0.36 | 0.40 | 0.15 |
| `area-map` | 609 | 0.32 | 0.30 | 0.00 |
| (leaf briefs) | 6,088 | 0.77 | 0.72 | |

Group 21 (auth-api, 9 leaves; 43 facts, 36 spanning), not tuned on:

| prompt | words | facts conveyed | spanning facts | detail share |
|---|---|---|---|---|
| `today` | 602 | 0.22 | 0.25 | 0.33 |
| `area-core` | 618 | 0.22 | 0.26 | 0.37 |
| `area-flows` | 573 | **0.34** | **0.33** | **0.15** |
| (leaf briefs) | 4,617 | 0.57 | 0.57 | |

`area-flows` is the pick: first or tied on both groups, about 1.7 times
today's facts at today's length, with the least detail. `area-core` ties it
on legal-api but falls to today's level on auth-api, where its parts list
and shared rules crowd out flows. The legal-api brief
(`data/upper/group-13/uppers.md`) is seven numbered flows (submit a filing,
create a business, staff review, delete or cancel, download a document,
COLIN sync, BN move), each step naming its part and function.

Both groups show a clustering problem the prompt cannot fix: their leaves
split one service by layer (two "auth-api service layer" leaves, legal-api
resources spread over four), so the leaf titles are hard to tell apart and
a flow has to cite several near-identical parts.

## Next

Round 1 candidates: `purpose-budget` and `blackbox-free`, revised: no "for whom",
a cap of the few hazards that change behaviour, and the condense GOTCHA rule
limited to what the code shows. Then the other three leaves (pay-api's
account models, entity-filer's filing processors, a payments architecture
document with its OpenAPI spec), and after that the upper brief.

## Reproduce

```
cd harness
CONDENSE_PROMPT=purpose-decisions uv run python pilot.py ~/hrono-eval/db/hrono.db \
  ../../2026-10-cluster-formula/data/detail/cond6-h4+g/assignment.npz 378 \
  ../data/condense-decisions $CACHE today purpose-budget decisions decisions-ctx
JUDGE_RUNS=2 uv run python judge.py ~/hrono-eval/db/hrono.db \
  ../../2026-10-cluster-formula/data/detail/cond6-h4+g/assignment.npz 378 \
  ../data/condense-decisions $CACHE
```

Round 1:

```
cd harness
uv run python pilot.py ~/hrono-eval/db/hrono.db \
  ../../2026-10-cluster-formula/data/detail/cond6-h4+g/assignment.npz 378 ../data $CACHE
```
