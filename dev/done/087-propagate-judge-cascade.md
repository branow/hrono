---
id: 087
title: `propagate` — judge cascade climbs a changed topic up the tree, marks ancestors stale (T36)
priority: high
size: big
depends_on: [085, 064, 059, 061, 057]
spec_refs: [build-order.md#T36, implementation-notes.md, clustering-lifecycle.md, summarization-experiments.md]
---

## Context
T36 and the LAST missing piece of hrono's full incremental promise. After `update`
(#085) places changed chunks and dirties LEAF briefs, the UPPER levels are still
stale-blind: #068's upper-node signature is its child NODE IDS, and a sticky-placed
leaf keeps its id, so a parent whose child's BRIEF changed is not detected by the
signature alone. `propagate` closes that: it judges each changed topic's new brief
against its stored one and marks ancestor briefs stale up the path — MARKS ONLY,
regenerates nothing (a later `brief`/`brief-upper` pass regenerates the marked
ones). implementation-notes: "propagate — judge each changed topic's source diff
vs its stored brief, mark ancestor briefs stale none/minor/major, write
update_log. Marks only, regenerates nothing."

## Description
A `propagate` op (judge role) that, for each leaf topic changed by `update`:
- **Judge call (T36.1)**: call the `judge`-role model+prompt (seeded #021) on the
  changed topic — its new content/brief vs the stored brief — returning a verdict
  none | minor | major. Batched per topic, BEST-OF-3 (the judge panel from
  summarization-experiments — majority verdict) so a single stochastic judgement
  doesn't mis-mark. Runs on the #057 client, OUTSIDE the #008 lock.
- **Cascade climb (T36.2)**: a `minor`/`major` verdict marks the topic's PARENT
  brief stale and climbs; `none` stops the climb. Marking is via the brief
  staleness mechanism (#064) — set the ancestor's brief stale, do not regenerate.
- **Drift counter + D_MAX (T36.3)**: accumulate a per-tree drift counter as
  changes climb; cap the climb at D_MAX (5) levels; the drift counter feeds the
  settle trigger (T39). Bake D_MAX.
- **update_log (T36.4)**: append to an `update_log` every judge verdict and each
  propagate/skip decision (topic, verdict, climbed-to level) — the audit trail the
  dashboard reads.
- MARKS ONLY (config-vs-work): propagate never runs brief/brief-upper; a subsequent
  `brief` pass regenerates exactly the marked-stale ancestors (selective, via #064).

## Acceptance criteria
- [ ] `propagate` judges each changed leaf topic (best-of-3, judge role via #057)
      and marks ancestor briefs stale on minor/major, stops on none; marks only,
      regenerates nothing.
- [ ] A single changed leaf whose brief materially changed marks its ancestor path
      stale up to the root (bounded by D_MAX); an immaterial change (none) marks
      nothing above the leaf.
- [ ] After propagate, a `brief`/`brief-upper` pass regenerates ONLY the marked
      ancestors (verified with an LLM call count — the affected path, not the tree).
- [ ] `update_log` records every verdict + propagate/skip decision.
- [ ] Judge runs outside the #008 lock; constants baked (D_MAX 5, best-of-3);
      deterministic marking given fixed judge verdicts (inject a fake judge in tests).
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- monitor / misfit (T37), repair (T38), settle/reconcile (T39).
- A one-command "incremental maintain" that chains update -> propagate -> brief
  (orchestration; fold into the maintain path once propagate lands).
- Changing the judge recipe (best-of-3 is settled).

## Review log
- 2026-08-25 PO: authored as T36, the upward-cascade piece that closes the full
  incremental promise (leaf placement #085 already done; this propagates a changed
  leaf brief up the tree). Judge role best-of-3, mark-only none/minor/major, drift
  counter + D_MAX feeding T39 settle, update_log audit trail. Constants baked.
- 2026-08-25 dev: implemented (commit 580a3b8). New `summarize/propagate.py` op:
  finds changed leaves (level-0 nodes whose stored brief member_signature no longer
  matches current #064 signature — exactly update's sticky-placed leaves), judges
  each best-of-3 via the judge role/#057 client OUTSIDE the #008 lock, `_majority`
  = median-of-3 over none<minor<major, `_verdict` parses the word from the reply.
  A minor/major climbs from the leaf marking each ancestor brief stale up to D_MAX
  (5) levels, bumps tree drift (minor 1 / major 2), and logs `propagated` with the
  top level climbed; `none` marks nothing and logs `skipped`. MARKS ONLY — the
  cascade never regenerates. Mechanism: migration 0019 adds `briefs.stale` (checked
  by #064's `_is_fresh`, set by new `briefs.mark_stale`, auto-cleared to 0 when a
  brief is regenerated via INSERT OR REPLACE), `tree_batch.drift`, and the
  `update_log` audit table. Seeded judge default template updated to elicit
  none/minor/major (its {source}/{summary} tokens now settled by this op; NOT added
  to _REQUIRED_PLACEHOLDERS — judge stays the unconstrained role the CRUD tests use).
  Registered in server/app.py. Tests (7): tests/summarize/test_propagate.py — pure
  majority + verdict parsing, registration, synthetic 6-deep chain proving climb is
  bounded at D_MAX=5 with update_log + drift, none-marks-nothing, unchanged-leaf-not-
  judged, and a maintain-harness integration proving brief-upper regenerates 0 nodes
  BEFORE propagate (parent looks fresh via #068) and only the marked path AFTER.
  Gate clean: 565 passed / 1 skipped. Ready for qa.
- 2026-08-25 qa: PASS (commit 580a3b8) -> po-review. Tree CLEAN at handoff.
  Verified the load-bearing upward-cascade end-to-end:
  - Built a 4-leaf -> 1-parent tree, edited one file, ran `update` (sticky-places
    the changed leaf, keeps its id). A `brief-upper` pass BEFORE propagate
    regenerated 0 nodes — the signature-blind gap (the parent's child-id signature
    is unchanged because the leaf kept its id). `propagate` judged best-of-3 (3
    judge calls), verdict major -> marked the parent stale, climbed_to=1, drift=2,
    logged `major/propagated`. A `brief-upper` AFTER regenerated exactly the marked
    parent. So propagate closes the gap AND stays selective (only the marked path).
  - Mechanism is correct: `_is_fresh` now returns false when `briefs.stale` is set
    (migration 0019), so #064's `stale_or_missing` picks up a propagate-marked
    ancestor; `briefs.upsert` (INSERT OR REPLACE) resets `stale` to 0 on regenerate
    (auto-clear). `mark_stale` never touches members (mark-only). Judge runs
    OUTSIDE the #008 lock (verdicts computed between the read and write blocks).
  - Recipe faithful: changed leaves = nodes whose current member_signature != the
    stored brief's; best-of-3 median verdict; minor/major climb marking ancestors
    up to D_MAX=5 (a 6-deep chain test proves the bound), none stops; drift bump
    (minor 1 / major 2); every verdict + propagate/skip logged to `update_log`.
    Constants baked. The leaf's own brief regenerates via #064 (its signature
    changed); propagate correctly handles only the ANCESTORS.
  - ruff clean; full suite 565 passed / 1 skip; 7 tests; atomic Conventional Commit.
  Non-blocking note for PO (same class as the #058->#066 hardening): the seeded
  `judge` prompt now consumes `{source}`/`{summary}`, but judge is still excluded
  from #066's `_REQUIRED_PLACEHOLDERS`, so a user editing the judge prompt to drop
  those tokens would silently degrade propagate (the replace no-ops -> judge sees
  no source/summary -> likely always "none"). The seeded default has them (works
  out of the box), so not a blocker; consider extending #066's validation to
  `judge: ("{source}","{summary}")` and updating the prompt-CRUD tests that use an
  arbitrary judge template. **T36 done -> the full incremental promise now holds
  up the whole tree: a change touches only affected nodes at every level.**
- 2026-08-25 PO review: PASS -> done. Tree clean, HEAD is #087's commit (580a3b8). Read propagate.py + migration 0019; ran the 7 propagate tests, ruff clean, full suite 565 passed / 1 skip. Faithful to the recipe: changed leaves = nodes whose current member_signature != their stored brief's (the sticky-placed leaves #085 kept ids for), judged best-of-3 (BEST_OF=3 median over none<minor<major) via the judge role/#057 client OUTSIDE the #008 lock; minor/major climbs marking each ancestor brief stale up to D_MAX=5 (a 6-deep chain test proves the bound), bumps drift (minor 1 / major 2) for the T39 settle trigger, logs every verdict to update_log; none marks nothing. MARK-ONLY: migration 0019 adds briefs.stale (read by #064's _is_fresh, set by mark_stale, AUTO-CLEARED to 0 on regenerate via INSERT OR REPLACE), so a later brief/brief-upper pass regenerates exactly the marked ancestors. qa drove it end-to-end: edit one file -> update (sticky-places leaf, keeps id) -> brief-upper BEFORE propagate = 0 nodes (the signature-blind gap) -> propagate major marks parent -> brief-upper AFTER regenerates exactly the marked parent. Constants baked. All acceptance criteria met. Closed. Spun off #088 for qa's note (extend #066's placeholder guard to judge's now-settled {source}/{summary} — #066 deferred judge because its tokens were unsettled; #087 settled them). **T36 done -> the FULL incremental promise holds at every level: a change touches only affected nodes, leaf to root (leaf #085/#064, ancestors #087). Remaining M7: T37 monitor / T38 repair / T39 settle (the maintenance layer).**
