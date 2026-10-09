---
id: 054
title: sections->tree mapping — cluster a named tree's own sections, not every embedded section
priority: high
size: medium
depends_on: [040, 138]
spec_refs: [build-order.md#T18, build-order.md#M4, build-order.md#M8, design-sketch-v1.md]
---

## Context
Spun off from #040 (cluster build) PO review. The `cluster` op names its output
tree by the job's `tree` string (default `"default"`), but there is no
`sections -> tree` mapping yet: `store.section_combined_vectors` loads EVERY
embedded section, so a build lumps all sources into one tree regardless of the
job's `tree`. That is correct for today's single-corpus world (M2/M3 have one
implicit corpus) and was rightly out of #040's scope, but it is a real
limitation the moment more than one tree/corpus exists.

This is deliberately parked, NOT authored into todo: with a single corpus the
"cluster everything into `default`" behavior is exactly right, and inventing a
trees table or a section->tree column now would be a speculative dead structure
(CLAUDE.md forbids). Pull it into todo when the FIRST second tree/corpus becomes
real.

## Trigger to pull into todo
When either lands and a build must scope to a subset of sections:
- M4 tree build introduces named trees as first-class (upper-level recursion
  needs to know which sections belong to which tree), OR
- M8 breadth adds multiple sources/corpora that should NOT cluster together.

## Description (when pulled in)
Give sections a tree membership and scope the build to it:
- A `sections -> tree` association (a column or a mapping table; decide with the
  M4 tree model — do not pre-build it here).
- `store.section_combined_vectors` filters to the requested tree's sections
  instead of loading all embedded sections.
- `cluster` op clusters only the named tree's sections; `replace_tree` already
  scopes nodes/coords by `tree`, so persistence is largely ready.
- Preserve today's behavior when there is one implicit tree (`default`).

## Acceptance criteria
- [x] A build over tree T clusters ONLY T's sections, not every embedded section.
- [x] Two trees over disjoint sections do not cross-contaminate members/coords.
- [x] Single-corpus behavior is unchanged (everything in `default`) when no
      explicit tree partition exists.
- [x] Baked clustering constants unchanged; still deterministic under the seed.
- [x] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The trees-registry / tree lifecycle itself (that is the M4 tree model; this
  only consumes whatever section->tree mapping M4 settles).
- Incremental placement (M7) and upper-level recursion (M4).

## Review log
- 2026-08-22 PO: spun off from #040 PO review. #040 met its own criteria; this
  captures the known `tree`-is-just-a-name limitation so M4/M8 confronts it
  rather than silently clustering across sources. Parked in backlog with a
  pull-in trigger (first real second tree/corpus); medium because M4 will need it
  soon.

- 2026-09-25 po: PROMOTED to todo, raised to **high**, and reframed. The park
  was conditional on a trigger, and the trigger has already fired — not by M4
  or M8, but by #138, which made the tree a REQUIRED ARGUMENT the user types:
  `hrono tree maintain <name>`, `hrono tree sync <name>`.

  Driven, not assumed. Two cluster runs over one six-section corpus, one named
  `alpha` and one `beta`:

      tree alpha: 2 nodes, 6 members
      tree beta:  2 nodes, 6 members
      sections held by MORE THAN ONE tree: 6

  Two trees, identical contents, every section in both. So the product accepts
  a tree name, echoes it back ("Started maintain job j for tree 'beta'"), and
  silently ignores it for section selection. That is no longer "correct for a
  single corpus" — it is a documented surface that does not do what it says.

  It also recasts this month's cross-tree defects. #158's F2 (a merge deleting
  another tree's membership) and #164's unguarded pool scope both concerned a
  section living in two trees, which I had taken for an exotic state worth
  guarding against. It is the DEFAULT outcome of running the documented command
  twice. Those two fixes are now load-bearing rather than defensive.

## The design, settled (2026-09-25 po)
This was left to "decide with the M4 tree model", and M4 is long done without
deciding it, so I am settling it rather than leaving dev to guess:

**A tree is a set of SOURCES, declared as registry config.** `trees` becomes a
registry collection like `sources`, `models` and `connections`, whose config
names the sources whose sections the tree is built from. Then:

- `section_combined_vectors` takes the tree's sources and filters on
  `sections.source IN (...)` — `sections.source` already names the registered
  source and `sections_source` is already indexed.
- A tree with no registry entry keeps today's behavior: every embedded section.
  That preserves the single-corpus case exactly and means no migration of
  existing databases changes what they contain.
- It follows the settled convention — config is data you PUT, work is a job you
  POST — so declaring a tree triggers nothing, and `maintain`/`sync` keep doing
  the work.

A per-section tree column is the alternative and it is worse: it duplicates
what `sections.source` already says, and it would have to be rewritten on every
ingest rather than declared once.

Reject a `maintain`/`sync` for a tree whose registry entry names a source that
does not exist — the same validation every other registry collection does.

- 2026-09-25 dev: done, commit 4e6f006. Built as the PO settled it — a tree is
  a set of SOURCES, declared as registry config — and the registry engine made
  that one descriptor plus one import, with no engine branch, exactly as #012's
  design promised.

  The defect had TWO doors, and the ticket only named one:
  - the build: `section_combined_vectors` loaded every embedded section. It now
    takes the tree's sources and filters on `sections.source`, which is already
    indexed.
  - the incremental path: `maintain` and `update` each iterated the WHOLE source
    registry regardless of the job's tree, so `hrono tree sync beta` would have
    pulled another tree's sources into beta even after the build learned to
    scope itself. Both now call `scoped_sources`.

  `sources_of` returns None, never `()`, and that distinction is what makes
  this additive: None means UNSCOPED — every embedded section, exactly what
  every existing database already does — while `()` would have silently emptied
  every tree nobody had declared. A test pins it, and the mutation that returns
  `()` instead fails 26 tests.

  The URL settled itself: `PUT /trees/<name>` is the config and
  `POST /trees/<name>/maintain` is the work, which is the convention stated in
  CLAUDE.md word for word. Nothing collided — the spec never settled tree
  config, which is the same gap that left this ticket parked past M4.

  CLI: the collection loop in `cli.py` was a HARDCODED tuple beside
  `COLLECTIONS`, so a new collection silently got no CLI — which is what
  happened here until I checked. It is now driven by `COLLECTIONS`, and `trees`
  hangs under `hrono tree config` rather than as `hrono trees`, because
  `hrono trees` next to `hrono tree` reads as a typo. Driven against a real
  server through the real CLI: `list`, `get`, and `set` from stdin all work.

  Driven live, the whole point of the ticket, with the real UMAP -> HDBSCAN
  recipe over 28 sections from two sources:

      PUT /trees/alpha {"sources":["alpha-src"]}   200
      PUT /trees/ghost {"sources":["nope"]}        400 "tree names unregistered
                                                       sources: nope"
      GET /jobs after both PUTs                    []      (config triggers no
                                                            work, as ruled)
      cluster alpha, cluster beta                  both succeeded
      tree alpha: 14 members, sources=[alpha-src]
      tree beta:  14 members, sources=[beta-src]
      sections in MORE THAN ONE tree: 0

  The same probe before the fix reported 6 of 6 sections in both trees.

  Mutations, all killed: the build ignoring the tree's sources -> 1 fail;
  `scoped_sources` returning every source -> 1; an undeclared tree meaning NO
  sources -> 26; a tree allowed to name an unregistered source -> 1.

  **One thing I could not make safe inside this ticket.** `hrono tree config rm
  alpha` — or `DELETE /trees/alpha` — puts alpha back in the UNSCOPED state, so
  the next `maintain alpha` clusters every source in the corpus into it. That
  follows directly from None meaning unscoped, and it is the right meaning for
  an absent row; what is wrong is that deleting one small config row silently
  arms a very large operation. The registry engine has a `validate` hook for
  WRITES and nothing for deletes, so refusing this needs a change to the engine
  and a decision about what a tree with nodes should do when its config is
  removed. Flagging rather than inventing either. Gate clean: 1134 passed.

- 2026-09-25 qa: PASS, to po-review. Every criterion met, and the second door
  dev found — `maintain` and `update` iterating the whole source registry — was
  the half that would have made the first half pointless.

  Gate re-run at 4e6f006: ruff clean, 1134 passed. I drove the CLI path myself
  against a real server: `hrono tree config list/get/set` all work, and `set`
  from stdin declared a third tree. The hardcoded collection tuple dev found in
  `cli.py` is the kind of duplication that fails silently — a new collection
  with no CLI — and driving it from `COLLECTIONS` closes that for the next one
  too. `hrono tree config` rather than `hrono trees` is the right call.

  Re-ran dev's U3 (`sources_of` returning `()` instead of None for an
  undeclared tree) over `tests/tree` and `tests/cluster`: **45 failures.** That
  is the blast radius of the None-versus-empty distinction, and it is the right
  shape — the mutation makes every undeclared tree empty, which is every tree
  in every existing database.

  **Found, filed as #166 at HIGH, and not a blocker: recall ignores the tree.**
  `POST /trees/<name>/recall` takes the tree in its URL and discards it —
  `engine.recall` has no tree parameter, `vector_leg.scores` runs
  `SELECT ... FROM passages ORDER BY id` over every passage in the database and
  says "EVERY embedded passage" in its own docstring, and `keyword_leg.scores`
  takes only the query. There is no parameter by which a tree could scope it.

  I established that by reading both legs, not by driving a leak, and I want to
  be exact about why: I built a two-tree corpus and asked tree alpha about
  beta's content, and recall correctly answered "no confident matches — explore
  the map", because #127's confidence gate refuses a corpus small enough to
  fabricate inline. The absence of a leak in that run is evidence about the
  gate, not about the scope. A real test needs a corpus large enough to clear
  it, which is part of why this is a ticket and not a line.

  It is not a regression: before #054 every tree held every section, so "the
  whole corpus" and "this tree's corpus" were the same set and the distinction
  could not be observed. #054 is what makes them differ — which is exactly why
  #166 should land before multi-tree is documented as working, and why I filed
  it high rather than leaving it in the backlog's middle.

  **For the PO: dev's flag about `rm` needs your ruling.** Deleting a tree's
  config row returns it to UNSCOPED, so the next `maintain` clusters every
  source into it. The meaning is right for an absent row — that is the whole
  additivity argument — and dev was right not to invent a refusal, because the
  registry engine has a `validate` hook for writes and nothing for deletes.
  My view: the engine wants a delete hook, and it is worth one ticket rather
  than a special case here.

- 2026-09-25 po: CLOSED, first round. A tree is now a map over what it says it
  is a map over, on both doors that write it.

  What I want recorded is how this was found, because the mechanism is
  reusable. The ticket had been parked for a month behind an explicit trigger —
  "when the FIRST second tree/corpus becomes real" — and the park was correct
  when written. It went stale silently, because the trigger fired through a
  door nobody was watching: #138 added a required `<name>` argument to
  `hrono tree maintain`, and nothing connected "the CLI now takes a tree name"
  to "a parked ticket is waiting for exactly that". Triage caught it only
  because I checked the trigger against the code instead of re-reading the
  park.

  **Every parked ticket with a pull-in trigger is a claim about the present
  that ages.** Backlog triage should test those triggers, not just re-read the
  reasons. I am not writing that as a convention ticket yet — one instance is
  an anecdote — but if the next triage finds a second stale trigger it becomes
  one.

  Ruling on `rm`, as qa asked: **a ticket, not a special case.** #167 authored
  for a delete hook on the registry descriptor, with the tree case as its
  motivating example. dev was right to flag rather than invent, and qa is right
  that the engine wants the hook — `validate` covers writes only, and "may this
  be deleted" is a question three collections will eventually have (a model a
  tree still references, a connection a source still uses). It is a footgun
  rather than a live defect: it takes a delete AND a subsequent maintain, and
  the tree's own config is one PUT away from being restored.

  **#166 promoted to todo at high, ahead of #163 and #161.** It is the read
  door, and #054 is what made the write and read sides disagree. A product that
  separates two maps correctly and then answers both from one pile is harder to
  trust than one that never claimed to separate them. It also carries a real
  design question — the z-score population — which I am NOT ruling on here; see
  the ticket.
