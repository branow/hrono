---
id: E059
title: a sync keeps the insights: a rewritten reviewed brief gets a new pass before its parent
priority: high
kinds: [backend]
depends_on: [E058]
outcomes: [O3]
journeys: [J4, J8]
waits_on: []
---

## Goal
A curator syncs a commit into a tree with insights on. Without this epic
the sync rewrites a reviewed area brief with the cheaper model and the
extension silently disappears. Rule (Orest, 2026-11-02): a rewritten brief
that had a pass gets a full new pass in the same sync, before its parent;
stored findings are not re-applied; a topic whose count first reaches the
threshold on a sync gets its first pass. Moves O3 (E054 535).

## Build on
- `tree/sync_chain.py` and the propagate path that rewrites stale upper
  briefs (`summarize/propagate.py`); the pass from E058 is called there,
  between a topic's `brief-upper` rewrite and its parent's.
- Brief versions keep 5 (E033): a re-pass writes more versions; make sure a
  run of re-passes never pushes out the only cheaper original a reader
  compares against (keep it, or say on the version list it is gone).

## Tickets

### 1 a rewritten reviewed brief is reviewed again in the same sync
Done when:
- [ ] a real commit synced into the flask copy that touches a reviewed
      topic's sections (at most 10 real calls, D2): the run's log shows that
      topic's brief rewrite, then its pass, then its parent's rewrite from
      the extended brief
- [ ] a topic not reviewed before whose count crosses the threshold on the
      sync gets its first pass; a topic below the threshold gets none
- [ ] a pinned reviewed topic: sync leaves its brief alone, the new
      findings are stored not applied (test)
- [ ] a test drives a sync through `tree/sync_chain.py` (not `build_tree`
      directly) and fails when the pass wiring there is removed or a sync
      runs passes on topics under the threshold (E058 qa: the
      `reviewing=False` guard had no test)

### 2 the version history keeps the cheaper brief a reader compares against
Done when:
- [ ] a test with six successive passes on one topic: the version list
      still holds a cheaper (non-insights) brief, or states that it is no
      longer kept
- [ ] docs/summarization.md and docs/architecture.md describe when a pass
      runs on build, settle and sync

### 3 the export's root page carries the root pass's findings
The root page keeps only the root brief's opening (`export/render.py`
`_routing`), so the root pass's findings, placed under the brief's
Conventions and hazard parts, never reach `root.md` (E058 qa). D9: the
root page keeps the opening plus the parts the root's extension wrote.
Done when:
- [ ] `hrono tree export` of the flask copy after the root pass: `root.md`
      states the root's findings (the dotenv precedence and the session
      lifetime rule are readable there), `grep -ri insight` stays empty
- [ ] an unextended root renders as today (test); the extended root page
      stays under 2.5 times the unextended one on flask, and the number
      goes in the epic's Log

## Out of scope
- Re-applying old findings to a new brief (the rule says a new pass).

## Tried

## Log
- 2026-11-02 po: created from E054 535 (O3).
- 2026-11-02 po: folded E058 qa followups: a sync-chain test for the pass guard (ticket 1), the root page carries the root's extension (ticket 3, D9).
