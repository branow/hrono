---
id: 064
title: member-set signature + prompt-hash brief invalidation (T23.2)
priority: high
size: medium
depends_on: [059, 040]
spec_refs: [build-order.md#T23.2, implementation-notes.md, clustering-lifecycle.md]
---

## Context
T23.2 — a load-bearing piece of hrono's differentiator (incremental update). A
stored brief must know when it is STALE so `brief` regenerates only what changed,
never the whole tree. Two triggers (implementation-notes: "Membership changes
mark briefs stale directly, bypassing the judge"; config edits "invalidate
exactly what that prompt produced ... a model edit invalidates its role's
outputs"):
1. **Member-set change**: the node's set of member ids changed since the brief
   was written.
2. **Prompt/model change**: the brief-role prompt template or the model that
   produced the brief changed (#059 already records the prompt template hash +
   model as provenance).

## Description
Give each brief a staleness signature and a check that marks stale without
regenerating:
- **Member-set signature**: a stable hash of the node's ordered member ids
  (sections for level 1, child node ids above). Store it with the brief at
  generation time (#059/#061).
- **Prompt/model signature**: reuse the provenance already stored (#059): prompt
  template hash + model name.
- A brief is FRESH iff its stored member-set signature equals the node's current
  members AND its prompt/model signature equals the currently-resolved brief-role
  prompt hash + model. Otherwise STALE.
- Wire invalidation: recomputing membership (a re-cluster) or editing the brief
  prompt/model marks exactly the affected briefs stale (a mark, never a
  regenerate — regeneration is the `brief` op #059, which should already skip
  fresh briefs and rebuild stale ones). This closes the loop with #059's
  skip-on-unchanged.
- Surface counts (fresh/stale) for the tree health read (implementation-notes
  `briefs: {fresh, stale}`).

## Acceptance criteria
- [ ] Each brief stores a member-set signature; a changed member set makes the
      brief compute as stale.
- [ ] A changed brief-role prompt template hash or model makes existing briefs
      compute as stale (via the stored provenance), unchanged config keeps them
      fresh.
- [ ] Invalidation only MARKS staleness; nothing regenerates automatically
      (config edit != run — honors the "writing config never triggers work"
      rule).
- [ ] `brief` (#059) regenerates stale briefs and skips fresh ones, driven by
      this signature; fresh/stale counts are readable.
- [ ] Tests: membership change -> stale; prompt-hash change -> stale; no change
      -> fresh; regen touches only stale. `ruff format`, `ruff check --fix`,
      `pytest` clean; committed.

## Out of scope
- The judge cascade / `propagate` (that is M7's none/minor/major ancestor
  staleness; here membership/prompt changes mark DIRECTLY, bypassing the judge).
- Actual regeneration mechanics (owned by #059).
- Source content-drift detection (that is the `sync` op, already done).

## Review log
- 2026-08-23 PO: authored as T23.2 — the incremental invalidation keys. Member-
  set signature + the prompt/model provenance #059 already records; mark-only
  (never auto-run), driving #059's skip/rebuild. High priority: this is the core
  incremental-update promise, not optional polish.
- 2026-08-24 dev: DONE, committed 8ce1c35, handoff to qa. Brief staleness is
  COMPUTED on read (no stored stale flag), so a config edit never triggers work
  (honors "writing config never runs"):
  - migration 0013 adds `briefs.member_signature`; `briefs.member_signature(conn,
    node_id)` hashes the node's ordered member ids (sections `s<id>` at leaf,
    child nodes `n<id>` above — prefixed so ids can't collide).
  - `_is_fresh` = stored member_signature == current AND stored prompt_hash +
    model_name == the resolved brief prompt hash + model (reuses #059 provenance).
  - `stale_or_missing` (drives #059's brief op, now wired to it) returns nodes
    with no brief OR a stale one; the brief op stores the current signature on
    (re)write. `counts` returns (fresh, stale) for the tree-health read.
  - Membership change -> stale; brief-prompt template hash change -> all stale;
    model change -> stale; unchanged -> fresh (skipped). Mark-only: nothing
    regenerates until the brief op runs.
  NOTE (process): a concurrent `git reset` (reflog) wiped my first uncommitted
  attempt and the working tree flip-flopped mid-edit — all committed work
  survived; I rebuilt 064 and committed immediately. Recommend the loop avoid
  `git reset --hard` on a shared tree while a dev has uncommitted WIP.
  Verified: ruff format/check clean; pytest 435 passed / 1 skip (+4: membership
  -> stale, prompt-hash -> stale, unchanged -> fresh+counts, membership -> counts
  shift). Left the pre-existing `.gitignore` edit out of the commit.
- 2026-08-24 qa: PASS (commit 8ce1c35) -> po-review. Verified every dimension:
  - Drove the load-bearing incremental behavior end-to-end through the REAL brief
    op: initial brief -> counts (2 fresh, 0 stale); a membership change on ONE
    node marks it (1 fresh, 1 stale) with NO run (mark-only, computed on read),
    then re-brief makes exactly 1 call (only the changed node); a brief-prompt
    template change marks ALL stale (0 fresh, 2 stale), then re-brief makes 2
    calls under the new prompt hash. This is hrono's core incremental-update
    differentiator, and it honors "writing config never runs" — no auto-regen.
  - Staleness is COMPUTED ON READ (no stored stale flag), so there is nothing to
    desync: `_is_fresh` = stored member_signature == current AND stored prompt_hash
    + model == the resolved brief prompt hash + model (reuses #059 provenance).
    Member ids are prefixed (`s<id>` sections / `n<id>` child nodes) so a section
    id and a node id can never collide into the same signature.
  - Migration 0013 adds `member_signature` NULLABLE, so briefs written before it
    compute stale and regenerate once — correct backward-compatible handling.
  - brief.py cleanly swaps `needing_brief` -> `stale_or_missing(prompt_hash,
    model)` and stores the current signature on (re)write; `counts` gives the
    (fresh, stale) tree-health read. Tests are regression-grade (membership->stale
    only that node, prompt-change->all stale, unchanged->fresh, counts shift).
  - Process: dev committed 064 with a CLEAN tree before handoff this time (good).
    A concurrent #061 (brief-upper) WIP was present in the tree during my review
    (new brief_upper.py + app.py registration + PURELY ADDITIVE `child_briefs` /
    `child_ids` helpers in briefs.py) — I confirmed it touches nothing 064 depends
    on and the full suite passed, so no isolation was needed and the gate is valid
    for 064's commit. ruff clean; 435 passed / 1 skip.
  Minor note (non-blocking): `stale_or_missing` and `counts` issue per-node
  `get` + `member_signature` queries in a Python loop (O(N) queries per level) —
  fine at current tree sizes; a set-based query is a future optimization if a
  level ever holds very many nodes. (Pre-existing unrelated `.gitignore` edit
  remains uncommitted, out of this ticket's commit.)
- 2026-08-24 PO review: PASS -> done. Read migration 0013 + briefs.py: staleness
  is COMPUTED ON READ (no stored flag), so a config edit never triggers work —
  honors "writing config never runs"; `member_signature` hashes the node's
  ordered member ids with `s<id>`/`n<id>` prefixes (no section/node id collision);
  `_is_fresh` = member-sig AND prompt_hash AND model all match the #059 provenance;
  migration 0013 is NULLABLE so pre-0013 briefs recompute stale and regenerate
  once (backward-compatible). Ran the 4 staleness tests, 29 summarize tests, ruff
  clean, full suite 441 passed / 1 skip (#064 committed 8ce1c35 with #061 f621cb6
  additive on top; tree clean, no isolation needed). All 5 acceptance criteria met
  — this is hrono's core incremental promise and it works (membership change ->
  only that node stale; prompt change -> all stale; mark-only). Closed. qa's
  O(N)-per-node-query note left as an observation, NOT ticketed (fine at current
  tree sizes; optimize if a level ever holds very many nodes — YAGNI).
  PROCESS: dev committed 064 with a CLEAN tree this time (good). But dev's note
  that a concurrent `git reset` wiped their first uncommitted attempt is a WORSE
  variant of the hygiene problem — shared-tree WORK LOSS, not just false gates.
  Folded into the pending stakeholder decision; strengthens worktree-per-ticket.
