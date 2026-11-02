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
- [ ] a tree row stored without `insights_threshold`: a sync does not pass
      every topic; it falls back to `INSIGHTS_THRESHOLD` as
      `registry/impact.py:657` does (test; `review.py:322` uses `or 0`)

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
- [ ] `hrono tree export` of the flask copy after the root pass: every
      line the root pass wrote is in `root.md` (whatever findings that run
      made; the .env precedence on round 1), `grep -ri insight` stays empty
- [ ] an unextended root renders as today (test); the extended root page
      stays under 5 times the unextended one on flask (ruled 2026-11-02, D10:
      round 1 measured 4834 vs 1111 bytes, 4.35x), number in the Log
- [ ] a root extended twice with no rewrite between: `root.md` carries both
      passes' lines (test; `briefs.cheaper_text` walks back to the last
      non-insights brief)
- [ ] docs/architecture.md:215 rewrapped to 80 columns

## Out of scope
- Re-applying old findings to a new brief (the rule says a new pass).

## Tried

## Log
- 2026-11-02 po: created from E054 535 (O3).
- 2026-11-02 po: folded E058 qa followups: a sync-chain test for the pass guard (ticket 1), the root page carries the root's extension (ticket 3, D9).
- 2026-11-02 dev: round 1 started.
- 2026-11-02 dev: ticket 1 e738992. Real run on a flask copy (sonnet as insights model, threshold 60000, a real CHANGES.rst commit on a copy of the mirror): sync log is brief rewrite of topic 17, pass on 17, rewrite of root 19 from the extended brief; repair then split topics, so 17 was rewritten again and got a second pass before 19 was rewritten again (rule held twice). Second sync with no change at threshold 40000: root got its first pass, topic 18 (39514 < 40000) none. Restarted the server between: passes and briefs unchanged. Real calls: 24 in the sync (4 insights), over D2's 10 because repair split 4 topics. Mutations: no review.run in _brief_upper_levels (3 sync tests fail); root=True (under-threshold test fails); no rebrief (first-pass test fails); pin guard removed in review (pinned test fails).
- 2026-11-02 dev: ticket 2 4296f26. Six-pass test; mutation: drop the MIN(id) keep in briefs._keep_replaced (both history tests fail). Docs in summarization.md and architecture.md.
- 2026-11-02 dev: ticket 3 (export commits). hrono tree export of the flask copy after the root pass: root.md states the dotenv precedence, grep -ri insight empty. Size: unextended root.md 1111 bytes, extended 4834 (4.35x), over the 2.5x bound: the pass's four findings alone are about 3.4 KB. Not met; PO to decide (raise the bound or cap). Mutations: cheaper_text without the passed_at guard (rewritten-root test fails); _routing ignoring cheaper (extended test fails).
- 2026-11-02 dev: fast suite 2130 passed; head 73fc4f9.
- 2026-11-02 qa: round 1 at 66fa020: ticket 3's size bound not met (root.md 4834 vs 1111 bytes, 4.35x > 2.5x; the root pass's changed lines are ~3.7 KB, so the bound cannot hold without dropping findings), returned to the PO as a ticket defect. Drove on a copy of dev's flask db: a no-change sync (0 model calls, insights 0/0/0), export (root.md states the .env precedence; the session lifetime rule was not among this run's root findings; grep -ri insight empty), registry dry run at 30000 (topics 18 and 19 listed); ledger of dev's sync confirms brief-upper, insights x2, brief-upper order twice. Re-ran dev's no-rebrief mutation (first-pass test fails). Added a failing-provider sync test (66fa020; bites when review swallows LLMError). Full suite green (2309). Followups: dev/backlog/E059-followups.md.
- 2026-11-02 po: ruled on round 1 (D10): ticket 3's bound is 5x, measured (4.35x on flask); the root page keeps every line the root pass wrote, so the named findings are whatever the run found; folded qa followups: two passes both on root.md, the threshold fallback, the architecture.md wrap. Token count went to E060.
- 2026-11-02 dev: round 2 (D10) at HEAD: re-exported the existing flask copy's root with the new code: root.md 4834 bytes vs 1111 unextended = 4.35x, under the 5x bound, every line the root pass wrote kept, grep -i insight empty. Added: test of a root extended twice (cheaper_text now walks back to the oldest pass version since the last non-pass version; mutation ORDER BY v.id DESC fails it), test of a tree row without insights_threshold (review.run falls back to INSIGHTS_THRESHOLD; mutation 'or 0' fails it), architecture.md paragraph rewrapped to 80. Fast suite 2311 passed. No new model calls.
- 2026-11-02 qa: round 2 at 2cb59c4: pass. Re-verified the D10 lines: `hrono tree export flask` over a served copy of dev's flask db (not a direct render): root.md 4834 bytes vs 1111 unextended = 4.35x, under the 5x bound; all 6 lines the root pass wrote are on root.md; grep -ril insight empty. cheaper_text two-pass test and the INSIGHTS_THRESHOLD fallback test both bite (re-ran dev's mutations: ORDER BY v.id DESC, or 0). architecture.md:211-227 within 80 columns. Full suite green (2311 passed, 4 skipped). No fixes. Followups: dev/backlog/E059-followups.md.
- 2026-11-02 po: accepted at 2cb59c4. A sync re-reviews a rewritten reviewed brief before its parent (log order brief-upper, insights, brief-upper twice on flask), a pinned topic keeps its brief, root.md carries all 6 lines the root pass wrote at 4.35x (D10), served `hrono tree export` checked. Followup (cheaper brief lost after more than 5 passes since a rewrite) folded into E060 ticket 2, where "What changed" diffs against it.
