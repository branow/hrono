---
id: 060
title: embed + cluster briefs into the next level up (T22.1)
priority: high
size: medium
depends_on: [059, 035, 039, 040]
spec_refs: [build-order.md#T22.1, design-sketch-v1.md, how-hrono-works.md]
---

## Context
T22.1, the first step of building upper tree levels. The tree is recursive:
cluster -> brief -> embed briefs -> cluster the briefs -> brief-upper -> ... to
root (implementation-notes: "Build is recursive; embed/cluster/brief recur per
level, no fixed-stage model"). This ticket makes the existing embed (#035),
path-blend (#039), and cluster (#040) pipeline run over BRIEF TEXT at level N to
produce the node grouping at level N+1 — proving the pipeline is level-agnostic
rather than section-only.

## Description
Generalize embed + cluster to operate on a level's briefs, not just leaf
sections:
- Embed the level-N briefs' text with the same #035 embed op (content-addressed
  by the brief's content hash, embed-once) — briefs become embeddable content
  like sections.
- Cluster those brief vectors with the same #040 build (UMAP-25 / HDBSCAN-leaf /
  attach), persisting level N+1 nodes whose MEMBERS are level-N nodes (not
  sections). The `nodes`/`node_members` schema (#040 migration 0009) already
  carries `level`; reuse it — a member is a node id at level N.
- Path-blend (#039) for briefs: OPEN QUESTION for dev — a brief has no file path
  the way a section does. Recommended default: blend on the node's tree-path /
  provenance identity if one exists, else fall back to content-only embedding for
  briefs (alpha effectively 0). Confirm against #039 before coding; do not invent
  a synthetic path.
- Keep it a job op / reuse the existing ops with a level parameter — no new
  clustering recipe, same baked constants.

## Acceptance criteria
- [ ] The #035 embed + #040 cluster pipeline runs over a level's briefs and
      persists level N+1 nodes whose members are level-N node ids.
- [ ] Brief text is embedded content-addressed (embed-once) like sections; a
      re-run re-embeds nothing unchanged.
- [ ] Clustering uses the same baked constants (UMAP-25 / min_cluster_size 5 /
      leaf / seed); deterministic.
- [ ] The path-blend decision for briefs is implemented and documented (per the
      open question), not guessed.
- [ ] Tests: a small planted set of briefs clusters into a coherent next level,
      members are node ids, coverage + determinism hold. `ruff format`,
      `ruff check --fix`, `pytest` clean; committed.

## Out of scope
- `brief-upper` generation of the parent brief text (T22.2 / #061).
- The recursion controller that repeats this to root (T22.3 / #062).
- Any change to the clustering recipe/constants.

## Review log
- 2026-08-23 PO: authored as T22.1. Reuse embed(#035)+blend(#039)+cluster(#040)
  on brief text to form level N+1; members become node ids via the level-aware
  0009 schema. Flagged the brief-path-blend open question (a brief has no file
  path) with a content-only fallback default.
- 2026-08-24 dev: DONE, committed 1d23a4a, handoff to qa. Added the
  `cluster-briefs` op (`cluster/levels.py`), migration 0012 `node_children`
  (parent_id/child_id both FK nodes; attached + similarity), plus
  `briefs.level_briefs` and `cluster.store.replace_level`.
  - Level-agnostic reuse: for source level N (job.scope {"level": N}, default 0),
    registers each level-N node's brief text as content (embed-once by content
    hash), runs the SAME #035 embed op to vectorise it, then clusters with the
    SAME #040 build (UMAP-25 / min_cluster_size 5 / leaf / seed — no new recipe)
    and persists level N+1 nodes.
  - Members are NODE IDS, not sections. `node_members.section_id` FKs sections so
    it cannot hold node ids; added `node_children(parent_id, child_id)` for every
    level above the leaf. Level 0 keeps node_members (sections).
  - RESOLVED the path-blend open question per how-hrono-works.md ("topics have no
    file path to blend"): briefs are CONTENT-ONLY (alpha=0) — the clustering
    vector is the brief's L2-normalised content vector, no combined vector, no
    invented synthetic path.
  - embed-once (tested): brief bodies embed on the first pass, a re-run encodes
    nothing. Heavy compute outside the #008 lock (register under lock -> embed ->
    load vectors -> build outside -> re-acquire to persist).
  - Coords not persisted for upper levels (section_coords is section-keyed;
    warm-init for upper levels is #T39 future) — noted, not speculative.
  Verified: ruff format/check clean; pytest 431 passed / 1 skip (+5 levels tests:
  registration, 20 planted briefs -> 2 coherent level-1 nodes, members-are-node-
  ids, full coverage, embed-once, cross-DB determinism). Real UMAP+HDBSCAN over
  brief vectors. Left the pre-existing `.gitignore` edit out of the commit.
- 2026-08-24 qa: PASS (commit 1d23a4a) -> po-review, with a PROCESS ESCALATION
  for the PO (below). The ticket's own commit is correct across every dimension:
  - Gated in ISOLATION (had to — see escalation): stashed dev's uncommitted WIP,
    checked the tree was clean at 1d23a4a, then ran the gate. ruff format/check
    clean; `tests/cluster/test_levels.py` 5 passed x5 stable (real UMAP+HDBSCAN,
    no segfault); full suite 431 passed / 1 skip x2. Restored the WIP after.
  - Level-agnostic reuse verified: registers each level-N node's brief text as
    content (embed-once by content hash), runs the SAME #035 embed + #040 build
    (baked constants, no new recipe), persists level N+1 nodes. Tests: 20 planted
    briefs -> 2 coherent level-1 nodes, each recovered cluster == one planted
    group, full coverage, deterministic across two DBs.
  - Members are NODE IDS: new `node_children(parent_id, child_id)` table
    (migration 0012, both FK nodes ON DELETE CASCADE) because node_members.
    section_id FKs sections; test asserts child_ids == the level-0 node ids.
  - Path-blend open question resolved correctly per how-hrono-works.md: briefs
    are CONTENT-ONLY (alpha=0, L2-normalised content vector), no synthetic path.
  - Lock discipline correct (load briefs under lock -> register content -> embed
    op [own lock discipline] -> load vectors -> build OUTSIDE lock -> persist).
  Observation for #062 (non-blocking): `replace_level` clears level N+1 and
  rebuilds with fresh node ids; if level N+2 already exists, its node_children
  (child_id -> old N+1 ids) cascade-delete on that rebuild. The recursion
  controller must rebuild bottom-up (or invalidate downward) so it never rebuilds
  a level under an existing parent level. Also: #040's build raises ClusterError
  when a level has too few clusterable briefs (all-noise) — #062 must stop the
  recursion before that (near root) rather than let the leaf fail.

  PROCESS ESCALATION (PO — this is the 4th occurrence of the recurring hygiene
  problem already noted in board.md): when 060 arrived in verifying, the working
  tree was NOT clean — dev had already started the NEXT ticket's WIP (#064
  member-set/prompt-hash invalidation: uncommitted edits to summarize/briefs.py
  [member_signature/stale_or_missing/counts], summarize/brief.py, tests, plus an
  untracked migration 0013_brief_member_signature.sql). That WIP changed
  `briefs.upsert`'s signature, so a plain `uv run pytest` reported 8 failed / 3
  errors (TypeError on the new required arg) — a FALSE failure signal that has
  nothing to do with 060. I isolated 060 by stashing the WIP and re-gating clean,
  then restored the WIP intact. 060 passes, but please reinforce with dev: commit
  AND route each ticket, leaving the tree clean, before starting the next
  ticket's WIP — uncommitted next-ticket WIP keeps forcing isolated re-gating and
  risks a false gate signal. (Pre-existing unrelated `.gitignore` edit also still
  uncommitted.)
- 2026-08-24 PO review: PASS -> done. Independently gated in isolation (confirming
  qa): stashed the uncommitted #064 WIP (-u, incl. the untracked 0013 migration),
  verified the tree was clean at 1d23a4a, ran the full suite -> 431 passed / 1
  skip, ruff clean on levels.py/store.py, then restored the WIP intact. Read
  levels.py: reuses the SAME #035 embed + #040 build over brief text (baked
  constants, no new recipe), content-ONLY blend for briefs (alpha=0, L2-normalised
  content vector — resolves the path-blend open question per how-hrono-works.md,
  no synthetic path), members are node ids via node_children (migration 0012, both
  FK nodes CASCADE), embed-once, heavy compute outside the #008 lock. All 5
  acceptance criteria met. Closed. Threaded qa's two constraints into #062 (the
  recursion controller): rebuild bottom-up because replace_level mints fresh node
  ids (a rebuild under an existing parent cascade-deletes its node_children), and
  stop recursion before #040 raises all-noise near root.
  PROCESS: acknowledged qa's escalation — the recurring uncommitted-next-ticket-
  WIP problem. Raising it as a decision to the stakeholder (structural fix:
  worktree-per-ticket or a commit-clean gate before routing to verifying), since
  four+ board reinforcements have not stopped it and it risks a false gate signal.
