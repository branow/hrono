---
id: E056
title: a sync places new sections by their condensation, as a build does
priority: medium
kinds: [backend]
depends_on: []
outcomes: [O6]
journeys: [J4]
waits_on: []
---

## Goal
A curator syncs a commit and expects new sections to land where a rebuild
would put them. Today `update` places new sections from their raw content
and condenses them after, so incremental placement reads a different vector
than the build (clustering blends the condensation embedding, E050). This
epic condenses first, then places, and re-checks the placement threshold
TAU (0.70) on the condensation vectors. Moves O6 (E054 ticket 506; D1).

## Build on
- `tree/update.py` already calls `condense` (after placement); move it
  before `cluster/placement.py` and embed the condensation with the same
  blend as `cluster/blend.py` uses on a build. No new op.
- The cluster-formula evaluation in
  `docs/evaluations/2026-10-cluster-formula/` for how TAU was measured.

## Tickets

### 1 update condenses new sections before placing them
Done when:
- [ ] a real commit synced into the flask copy (one changed and one new
      file, at most 10 condense calls, D2) places each new section by the
      blended condensation vector: the run's log shows condense before
      place, and each placed section's stored vector equals the build's
      blend of its condensation
- [ ] with no condense model registered, update still places (raw vector,
      as today) and says so in the run's outcome
- [ ] the update tests assert the order condense, embed, place

### 2 TAU re-checked on condensation vectors
Done when:
- [ ] own-centre similarity of the flask copy's placed sections on the
      blended condensation vectors, with the share above and below 0.70,
      is written to `docs/evaluations/2026-11-tau-condensed/` with the
      script; TAU changes only if the numbers say so, and the note says why

### 3 an older install gets the current brief, condense and judge defaults
Change: list the earlier shipped hashes of the `brief`, `condense` and
`judge` defaults in `superseded` (`registry/collections/prompts.py`), as
E055 did for `brief-upper` (from git history); an edited prompt stays.
Done when:
- [ ] `hrono serve` on the flask copy (it holds the 2026-10-09 defaults)
      replaces the untouched `brief`, `condense` and `judge` rows with the
      current defaults; a restart changes nothing more
- [ ] a test holding each first-shipped text fails without the hashes;
      an edited prompt survives the upgrade

## Out of scope
- Re-placing sections already in the tree.

## Tried

## Log
- 2026-11-02 po: created from E054 506 (O6, D1); 506 was dropped on
  2026-10-12 for a different reason (E29) and is back as the placement gap
  E050's log names.
- 2026-11-02 po: ticket 3 added from E055 followups (old defaults on the flask copy are never upgraded, and this epic condenses with that prompt).
- 2026-11-02 dev r1: T3 7549fcc, T1 64000d6 (+docstring), embed fix (old condensations without a body never embedded; flask copy had 1312) , T2 eval docs/evaluations/2026-11-tau-condensed (TAU kept 0.70). Real app on flask copy: prompts replaced, restart no change; update job condensed 2 then placed (log order, stored vector = blend, diff 0). No-model path tested + shared-corpus error driven. Mutations: condense moved after place -> 2 tests fail; hashes removed -> 3 fail; embed registration removed -> 1 fails. Fast suite 2106 pass.
- 2026-11-02 qa r1: pass at 539fbd5. Drove update on a fresh flask copy (changed + new + empty + latin-1 file: 1 condense call, condensations 15:03:19 < embed 15:03:23 < place 15:03:24, each placed section's vector = blend of its condensation, raw differs); serve replaced all 4 prompts, restart changed nothing, a curator-edited judge prompt survived; no condense model -> placed raw, outcome says so; failed provider recovered by next run. Fixed 6d04627: any condense LLMError (provider down) was reported as "no condense model" and the sync succeeded placing raw; 539fbd5 architecture.md order. Mutation re-run: condense after placement -> test_update_places_a_new_section_by_its_condensation fails. History check: every earlier condense/brief/judge default hash is in superseded. Full suite 2286 green. Followups: dev/backlog/E056-followups.md.
- 2026-11-02 po: accepted at 539fbd5. A sync now places new sections by the blended condensation vector a build clusters on (log order and stored vector = blend on the flask copy), a provider failure stops the sync instead of placing raw, TAU kept at 0.70 with the numbers in docs/evaluations/2026-11-tau-condensed, older installs get current defaults. Followups (default-tree condensations, old-model condensations, ambiguous model) stay in backlog/E056-followups.md: none blocks O6.
- merged: main at 22f56cc
