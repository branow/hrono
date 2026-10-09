---
id: 071
title: brief passages into the same passage store, addressed `node://` (T25.3)
priority: high
size: medium
depends_on: [059, 030, 069, 070]
spec_refs: [build-order.md#T25.3, how-hrono-works.md]
---

## Context
Briefs are recallable too (how-hrono-works.md): every brief is markdown, so it
goes through the SAME splitter (#029/#030) into the SAME passage store, tagged
`source_type='node'`, and is embedded (#069) + FTS-indexed (#070) identically.
Recall then runs over the UNION of source and brief passages — architectural
questions surface brief passages (cross-cutting facts no single section states),
detail questions surface source passages, each hit tagged summary vs source.

## Description
- After a brief is written (#059 / #061), split its markdown into passages via
  the existing packer and store them in the passage store with
  `source_type='node'`.
- Address each brief passage:
  `node://hrono/nodes/<id>/<title-slug>@<member-signature>` — the topic's title
  slug in the path (so path-blend has semantics), the member-set signature
  (#064) as the opaque version. A brief whose signature changed re-splits (its
  old `node://...@<oldsig>` passages are replaced).
- Brief passages are embedded (#069) and FTS-indexed (#070) exactly like source
  passages; recall (later) unions both.
- Tag each passage's origin (summary vs source) so #075 can label hits.

## Acceptance criteria
- [ ] A written brief is split into passages in the shared passage store, tagged
      `source_type='node'`, addressed `node://hrono/nodes/<id>/<slug>@<sig>`.
- [ ] Brief passages are embedded (#069) and FTS-indexed (#070) like source
      passages; a signature change replaces the node's brief passages.
- [ ] Each passage carries an origin tag (summary vs source) for hit labelling.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The recall query/fusion (#072-075) — this only populates the store.
- Upper-level brief passaging beyond reusing the same path for any node id.

## Review log
- 2026-08-24 PO: authored as T25.3. Briefs -> same splitter -> same passage store
  under `node://.../@<member-signature>`, embedded + FTS-indexed like source
  passages, origin-tagged, so recall unions source and summary passages.
- 2026-08-25 dev: DONE, committed e994d3f (+ fix 81c7aa0), handoff to qa. Added
  `recall/brief_passages.py` `store_brief(conn, node_id, brief_text, signature)`:
  runs the brief markdown through the SAME splitter and stores a brief section +
  its passages tagged `source_type='node'`, addressed
  `node://hrono/nodes/<id>/<slug>@<signature>` (slug from the brief's first line,
  member-signature #064 as the version). Per-node `source` key `node-<id>` scopes
  the replace: a signature change clears the old brief section (passages cascade)
  + its FTS rows, then re-stores. Wired into #059 brief + #061 brief-upper after
  each upsert. Brief passages are embed-once (#035) + FTS-indexed (#070) like
  source passages; origin tag = `source_type='node'` for #075 labelling.
  Kept brief sections OUT of clustering + condensing by filtering
  `source_type != 'node'` in cluster.store.section_combined_vectors and
  summarize.store.pending (so briefs never become topics or get condensed).
  RECONCILED with #065 maintain: added a final embed pass after build-tree so
  node:// brief passages get vectorised in-run; relaxed the maintain incremental
  test to its true invariant (condensations + SOURCE embeddings unchanged on a
  second run) — brief-passage vectors churn while cluster/brief rebuild with fresh
  node ids (known M4 limit, #068).
  Verified: ruff clean; pytest 479 passed / 1 skip (+4: node:// addressing +
  origin tag; embeddable + FTS-indexed; signature-change replacement; node
  sections excluded from cluster + condense).
- 2026-08-25 qa: PASS (commits e994d3f + 81c7aa0) -> po-review. Tree CLEAN at
  handoff. Verified every dimension incl. the cross-cutting risk:
  - Drove maintain end-to-end over a real git repo: briefs land as `node://
    hrono/nodes/<id>/<slug>@<sig>` sections + passages (source_type='node'), ALL
    brief passages embedded (#035) AND FTS-indexed (#070), and — the load-bearing
    check — cluster `node_members` reference ONLY source ('git') sections, so
    briefs never become topics.
  - The exclusion is in the two right places: `cluster.store.section_combined_
    vectors` and `summarize.store.pending` both filter `source_type != 'node'`, so
    briefs are kept out of clustering AND condensing (also unit-tested directly).
  - Per-node `source` key `node-<id>` scopes the replace: a signature change
    clears the old brief section (passages cascade) + FTS rows then re-stores
    (tested — versions collapse to the new sig).
  - maintain reconciliation is correct + honest: the fix adds a final embed pass
    after build-tree so node:// brief passages get vectorised in-run, and the
    relaxed incremental test asserts the TRUE stable invariant — condensations +
    SOURCE-section embeddings unchanged on a second run — while documenting that
    brief-passage vectors churn under the known fresh-node-id limit (#068). Not
    hiding a regression; correctly narrowing the invariant.
  - ruff clean; full suite 479 passed / 1 skip. Two commits (feat + a maintain
    reconciliation fix directly caused by this change) — coherent.
  Non-blocking note for PO: the synthetic `source` key `node-<id>` shares the
  `sources.source` namespace, so a user source literally named `node-5` would
  overlap a node's brief-passage source key. Extremely unlikely (git sources
  aren't named that) and briefs are internal, but reserving the `node-` prefix in
  source-name validation would remove the overlap entirely if ever tightened.
  (Pre-existing unrelated `.gitignore` edit remains uncommitted.)
- 2026-08-25 PO review: PASS -> done. The ruff E501 I flagged on the WIP is fixed
  (dev committed clean at e994d3f + fix 81c7aa0). Gated #071 in an isolated
  worktree at HEAD (tree carried untracked #072 WIP): ruff clean, full suite 479
  passed / 1 skip. Verified the LOAD-BEARING exclusion is in BOTH right places —
  `source_type != 'node'` filters in `summarize/store.pending` (briefs not
  condensed) AND `cluster/store.section_combined_vectors` (briefs not clustered),
  so a brief can never become a topic. `node://hrono/nodes/<id>/<slug>@<sig>`
  addressing correct; per-node `source` key `node-<id>` scopes the replace
  (signature change clears old section + FTS, re-stores). The #065 maintain
  reconciliation is honest — a final embed pass vectorises node:// passages
  in-run, and the incremental test was narrowed to the TRUE stable invariant
  (condensations + SOURCE embeddings unchanged; brief-passage vectors churn under
  #068's known limit), not hiding a regression. All acceptance criteria met.
  Closed. Spun off #076 for qa's namespace note (reserve the `node-` prefix in
  source-name validation so a user source `node-5` cannot collide with a node's
  brief-passage source key). Did NOT hold #071 for it (improbable, internal).
