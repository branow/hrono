---
id: 100
title: A pure rename ejects the file from its cluster instead of being handled in place
priority: high
size: small
depends_on: []
spec_refs: [build-order.md#T34.3]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F27
---

## Context
T34.3 specifies moved/renamed files are handled **in place**, reusing the
content vector. `diff` does classify `moved` and `reconcile` does reuse content
by hash — but `placement.place` never sees the classification and re-scores the
section like any other delta.

## Description
`git mv source/utilities.js source/util-helpers.js` (content byte-identical),
then `update`:

```
  embeddings before: 1791
  embeddings after:  1792     (content NOT re-embedded; +1 is the new path string)
  old path rows: 0 | new path rows: 1
  section 196 source/util-helpers.js -> node None
  pending: {'path': 'source/util-helpers.js', 'batch': 4}
```

The section left node 2 and was parked in the incubator. With `alpha = 0.5` the
path component is half the blended vector's norm, so a rename alone can drop a
section's similarity to its own centroid below TAU 0.70 — and generic placement
then treats it as homeless. Combined with 095 (nothing drains the pool) the
rename permanently removed a working member from the tree.

Work:
- Use the `moved` classification in placement: keep the existing membership and
  re-stamp the path (content unchanged means the topic is unchanged).
- Refresh the node's content signature accordingly (content hashes are the
  signature basis, so a rename should not change it).
- Consider whether a rename should count as churn/drift at all.

## Decision (2026-09-12, dev — technical call, no PO input needed)

`placement.place` takes the `moved` classification from `diff` and short-circuits
it: keep the existing node membership, re-stamp `path`/`uri`/`version`, leave
`assignment_similarity` as it was, and do not touch the node's content signature
(content hashes are the signature basis, so a rename must not change it).
A rename does not count as churn/drift — the topic did not change.

## Acceptance criteria
- [ ] A pure rename keeps the section in its node; membership count unchanged.
- [ ] No re-embed of content, and no incubator parking, for a rename.
- [ ] Regression test: rename a clustered file, run `update`, assert same node.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-15 dev: started; moved to in-progress.
- 2026-09-15 dev: implemented and committed as `f58e614`, per the Decision
  block.

  **The change, in three parts.**
  1. `cluster/placement.py`: `moved` no longer goes through the sticky
     re-check. `_in_place` re-attaches the section to `prior_node_id` with the
     similarity and forced flag its predecessor had, and counts it as `stayed`.
     Nothing touches the node's content signature — it is built from member
     content HASHES and the hash is unchanged, so the brief does not go stale
     either; the tests assert the signatures are byte-identical across a
     rename. No coordinate is needed (#101 untouched): the section did not
     move in the space.
  2. `ingest/reconcile.py`: the deltas now carry the membership that is about
     to be destroyed — `prior_similarity`, `prior_forced` and `prior_batch`
     beside the existing `prior_node_id` — because `_drop_path` deletes the old
     section row and its membership cascades away, so after that moment there
     is no record left to re-attach from. `_OldSection` became a small frozen
     `_Old`; `_consume` returns the matched entry rather than just its node id.
  3. `cluster/store.py` gains `membership()` (node + similarity + forced) and
     `cluster/incubator.py` gains `parked_batch()`, the two reads that carry
     needs. `section_node` is untouched for its other callers.

  **One case the Decision does not name, decided here: a move that changes the
  file's EXTENSION is not an in-place move.** The split is grammar- and
  budget-dependent, so `a.md -> a.json` re-splits the same bytes into different
  sections; those sections pair by ORDINAL, not by content hash, and they are
  genuinely new content for placement. `_match` therefore downgrades them to
  `changed`, which makes the invariant behind part 1 true by construction: a
  delta of kind `moved` always has byte-identical content. Pinned by
  `test_a_move_that_re_splits_the_file_is_a_change_not_a_move`.

  **The parked-file rename (asked for explicitly).** A parked chunk has no
  membership to preserve, so it takes the placement rule again — its new path
  may well place it, which is the best outcome available. If it parks again it
  keeps the batch it was ALREADY parked at, carried through `prior_batch`.
  Why: the pool row is keyed `(tree, section_id)` since #095's migration 0022
  and a rename creates a NEW section id, so the old row cascades away and a
  naive re-park would stamp the current batch. That would reset the age clock,
  and a file renamed every few batches would never reach `MAX_AGE` — an
  unbounded pending state, exactly what #095's invariant forbids. The chunk has
  been homeless since its original batch and a rename does not change that.
  Consistent with the rest of #095: `park` keeps the earliest wait
  (ON CONFLICT DO NOTHING), a join still unparks, `sweep` still retires rows a
  rebuild homed, and `assert_pool_invariant` is asserted in every new
  update-level test.

  **Real-corpus proof** — the same rename, the same database, both code
  versions. On a COPY of `.e2e/run2/.hrono/hrono.db` and a COPY of
  `.e2e/run2/repos/chalk` (`.e2e/` never written: `run/.hrono/hrono.db` mtime
  still 2026-09-03 20:54:49, the chalk worktree still clean at `99818a2`),
  driving the REAL `update` op with the REAL MiniLM encoder, after confirming a
  no-change update is a clean no-op:

  ```
  git mv source/index.js source/entry-point.js
  OLD (HEAD 9e01051): entry-point.js node=None   members 73 -> 72
                      pending += ('source/entry-point.js', 5)      <- F27, live
  NEW (f58e614):      entry-point.js node=4      members 73 -> 73
                      pending unchanged, node signatures unchanged
  ```
  The database still carries F27's own casualty (`source/util-helpers.js`
  parked at batch 4) — this ticket stops the ejection happening again; re-homing
  that existing row is #095's drain/age, which is already wired.

  **On "no re-embed":** the second consecutive rename costs **+1 embedding**
  (1044 -> 1045) — the new path string — exactly as F27 measured. The FIRST
  rename against this database costs +16, and that is not the rename: this
  database was built before #097, so re-splitting the file under the current
  packer produces 15 new passage bodies. Both old and new code show the same
  +16, so it is not caused by this change; the second rename, whose passages
  were already produced by the current packer, isolates the true cost.

  Tests (9 new, 707 total), each verified regression-grade by mutating the
  source and watching the matching test go red:
  - `tests/tree/test_update.py` (the real `update` op over a git repo):
    `test_a_pure_rename_keeps_the_section_in_its_node` (same node, same
    similarity, membership count, no parking, signatures untouched);
    `test_a_rename_preserves_a_recorded_similarity` (drives a real join first
    so the carried number is non-None — without it the fixture's NULL
    similarity hides a dropped carry); `test_a_rename_does_not_re_embed_the_
    content` (+1 vector, the path); `test_a_rename_that_changes_the_grammar_
    is_a_normal_change`; `test_renaming_a_parked_chunk_keeps_the_wait_it_has_
    served`.
  - `tests/cluster/test_placement.py`: the carried node/similarity/forced, the
    no-membership case taking the placement rule, and the preserved park batch.
  - `tests/ingest/test_reconcile.py`: the extension-change downgrade and the
    membership carry.
  Mutations checked: re-scoring a move (fails the real-op test), resetting the
  park batch, dropping the similarity/forced carry in placement and again in
  reconcile, removing the `changed` downgrade, and not reading the membership
  at all — each fails at least one test.

  Not touched: #103, #102, #105, #113, #114, #101, #110.
  Gate clean: `ruff format` (225 files unchanged), `ruff check --fix` (all
  checks passed), `pytest` **707 passed**. Handing off to verifying.
- 2026-09-15 qa: **PASS — to po-review.** No defects in the commit. I
  reproduced the A/B on the real database and it matches dev's report exactly,
  and the carry survives every adversarial ordering I could build. One
  PRE-EXISTING issue surfaced along the way, filed as backlog #120.

  **1. The carry — safe, and fail-loud if it ever were not.** The dangerous
  case is `prior_node_id` naming a node that is gone by the time `_in_place`
  re-attaches. It cannot happen, by construction: `place()` applies every delta
  first and only then runs `_dissolve_sweep`, and nothing between `reconcile`
  (which captures the membership) and `place` deletes a node —
  `_drop_path` cascades MEMBERSHIPS away but leaves the node row, `embed` in
  between touches neither, and the single worker means no other op interleaves.
  Driven, not just argued: I deleted BOTH of a node's other members and renamed
  the third in the SAME batch. `_in_place` re-attached the renamed section to
  node 1, the two deletions marked node 1 affected, the sweep saw one member and
  dissolved it, and the survivor was re-placed into node 2 — `nodes [1,2,3] ->
  [2,3]`, no dangling membership, invariant clean. I also renamed every member
  of the smallest node at once: all three re-attached, still one node.
  And the defensive answer to "what if the carry ever DID go stale": I forced a
  delta with a ghost `prior_node_id` through `place()` and it raises
  `sqlite3.IntegrityError: FOREIGN KEY constraint failed` — `INSERT OR IGNORE`
  does not swallow FK violations, so a stale carry fails the job loudly rather
  than writing a dangling member.

  **2. The extension downgrade is right, and the inverse is impossible before
  it even matters.** `_match` pairs by content hash first and only falls back to
  ordinal, tagging the delta `changed` whenever the hash pairing failed — so a
  move onto a new extension (same file bytes, different grammar, different
  section boundaries, different section hashes) arrives as `changed` and takes
  the sticky path. Driven: `f3.txt -> f3.md` did NOT stay put, it was re-scored
  and re-placed. It costs nothing that a same-extension rename keeps: the FILE
  bytes are identical either way, so `contents` is reused; only the new SECTION
  bodies are new, which is exactly what a different split means, and that is
  content the corpus did not previously hold.
  The inverse — `git mv` plus an edit in one commit — cannot reach `moved` at
  all: `diff.py:53-63` detects a move by FILE content hash
  (`added_by_hash[removed[old_path]]`), so an edited-and-renamed file has no
  hash match and is classified deleted + new. I drove it and confirmed no
  `moved` change is emitted. The `_match` downgrade is a second, independent
  belt behind that.

  **3. The park-batch rule closes the evasion.** Parked an alien chunk at batch
  1, then renamed it once per run for six consecutive runs (a fresh section id
  and a cascaded pool row every time): the pool row kept batch 1 throughout —
  `pending=[('alien/zz0.txt', 1)] ... [('alien/zz4.txt', 1)]` — and the chunk
  aged out on the run past `MAX_AGE` exactly as an un-renamed one would.
  `assert_pool_invariant` held after every run. Without the carry a
  periodically-renamed file would never age.
  One design note, not a defect: `prior_batch` is carried for every delta kind,
  so a CHANGED file whose predecessor was parked also inherits the old wait.
  That is the same protection against evasion-by-editing, and defensible, but it
  is broader than the ticket describes.

  **4. Signatures and briefs — the claim holds; the run2 anomaly is not this
  commit's.** On a consistently built tree a rename leaves every node signature
  byte-identical (measured before/after on the fixture: `signatures identical:
  True`), leaves member count unchanged, adds no `update_log` row, and leaves
  `tree_batch.drift` at 0 — drift is only ever incremented by `propagate`
  (`propagate.py:166`), and a rename generates no propagate work, so a rename is
  genuinely not churn.
  On the real run2 database the NEW code DOES rewrite node 4's signature, and I
  chased it to the bottom rather than accept it: node 4's member CONTENT HASHES
  are identical before and after (the renamed section 86 carries the same
  `2a612447744a`), but the value stored in that database was never the signature
  of those members. Recomputing every node in the untouched base database shows
  **3 of 7 stored signatures already disagree with their members** (nodes 3, 4
  and the level-1 root 7). `add_member` recomputes on write, so the rename
  CORRECTED a stale value; it did not change what the signature should be.
  Dev's claim is therefore accurate. Filed the underlying problem as backlog
  **#120** (leaf signatures drift on cascade deletes; upper-level signatures are
  structurally the empty-set hash because `node_content_signature` reads
  `node_members`, which level >= 1 nodes do not have). Consequence for the
  re-run, worth knowing: the first membership write to nodes 3, 4 or 7 will
  refresh their signature and #064 will re-brief that node once — a one-off cost
  from the pre-existing staleness, not from this change.

  **5. The A/B reproduced on a COPY of `.e2e/run2/.hrono/hrono.db`**, real
  `update` op, real minilm encoder, both code versions, same rename
  (`benchmark.js -> bench/suite.js`, a working member of node 4):

  ```
  OLD 9e01051: node 4 -> None   members 73 -> 72   pending += (86, 5)   emb +3
  NEW f58e614: node 4 -> 4      members 73 -> 73   pending unchanged    emb +3
  ```

  Exactly dev's result: the old code ejects a working member on a pure rename
  and parks it; the new code keeps it. On the cost claim — **the two versions
  cost the SAME +3 embeddings**, so the fix adds no embedding work; the +3 is
  this database's pre-097 packing plus the new path string, and a second
  consecutive rename on a current-packer tree costs +1 (the path string alone),
  which I measured on the fixture. "A rename never re-embeds content" holds.
  (`.e2e/` was read-only throughout: repos copied to scratch and the registry
  URLs re-pointed at the copies; both run databases' mtimes unchanged, the e2e
  repos' worktrees still clean.)

  **Mutation-verified by me** in a worktree at `f58e614` (`PYTHONPATH` asserted
  inside it), each behaviour pinned by the tests named for it: `moved` routed
  back through the sticky re-check -> `test_a_moved_section_is_re_attached_on_
  the_terms_it_had` and `test_a_pure_rename_keeps_the_section_in_its_node`; the
  extension downgrade dropped -> `test_a_move_that_re_splits_the_file_is_a_
  change_not_a_move`; the park-batch carry dropped -> `test_a_renamed_parked_
  section_keeps_its_original_batch` and `test_renaming_a_parked_chunk_keeps_the_
  wait_it_has_served`; the similarity/forced carry dropped ->
  `test_a_moved_section_is_re_attached_on_the_terms_it_had` and
  `test_a_rename_preserves_a_recorded_similarity`.

  Commit `f58e614` is a clean Conventional Commit, atomic, 7 files, no stray
  changes; `.gitignore` is still the pre-existing uncommitted line. #103, #102,
  #105, #113, #114, #101 and #110 all left alone.

  Gate re-run by me on `f58e614`: `ruff format --check` 225 files unchanged,
  `ruff check` clean, `pytest` **707 passed** in 43.4s. Acceptance criteria hold.
- 2026-09-15 PO: **ACCEPTED -> done.** Commit f58e614. Verified independently.

  **Gate re-run by me:** `ruff format --check .` 225 files already formatted;
  `ruff check .` all checks passed; `uv run pytest` **707 passed** in 44.3s.

  **Diff read.** The fix is right in kind, not just in effect: a rename is not
  churn, so it should not be re-scored at all. Re-scoring it was the bug —
  with ALPHA 0.5 the path is half the blended vector's norm, so a rename alone
  could drop a working member under TAU and park it. Carrying
  `prior_similarity` / `prior_forced` / `prior_batch` through `reconcile` is
  necessary rather than convenient, because `_drop_path` destroys the
  membership before placement runs and that row is the only record of it.

  **Both cases dev added beyond the Decision are good judgement, and I want them
  called out rather than absorbed.**
  - The extension-CHANGING move downgraded to `changed` makes "a moved delta
    always has byte-identical content" true BY CONSTRUCTION rather than by
    assumption. A different grammar and budget means the sections pair by
    ordinal, not content hash, so they are genuinely new content. Turning an
    invariant the code relies on into something the code enforces is the right
    instinct.
  - Keeping a parked file's ORIGINAL park batch closes an evasion nobody asked
    about: since the pool is keyed by `section_id` (0022), a naive re-park would
    reset the age clock, so a periodically renamed file could evade `MAX_AGE`
    for ever. That is the kind of second-order thinking I want on lifecycle
    code.

  All acceptance criteria hold; qa drove the hard cases (concurrent dissolve,
  ghost `prior_node_id` failing on the FK rather than writing a dangling member,
  `git mv`+edit provably unable to reach `moved`) and the A/B showed no extra
  embedding cost.

  **On #120 — I investigated it myself, and HALF OF IT IS NOT A DEFECT.**
  This matters enough to state precisely, because the ticket as filed would send
  a dev chasing a phantom.
  - **The leaf half is REAL, and I confirmed the mechanism rather than inferring
    it.** On a copy of `.e2e/run2/.hrono/hrono.db` I recomputed every node's
    signature against its members: leaf nodes **3 and 4 disagree** with their
    stored value. I then demonstrated the cause directly — took node 1 (whose
    signature agreed), deleted one member section, and watched the
    `node_members` row cascade away while the stored signature stayed
    untouched: agreement True -> False in one statement. Cascade deletes drift
    the signature. Confirmed.
  - **The upper-level half is NOT real — it is a category error in the
    diagnostic.** qa reported that upper signatures are "structurally the
    empty-set hash". They are not. Node 7 (level 1) stores **exactly the
    child-id signature** `_signature(f"n{cid}" ...)` that `replace_level` writes,
    and it is NOT the empty-set hash — I checked both. The apparent
    "disagreement" comes from applying `node_content_signature`, a LEAF function
    over `node_members`, to an upper node that legitimately has no members: of
    course it returns the empty-set hash and differs. Nothing ever stores that.
  - **And it is not latent either.** I traced every caller of the three
    members-based refreshers and each target is provably level 0:
    `add_leaf_node` hardcodes `level 0`; `placement.py:134` takes its node from
    `membership()`, which filters `nodes.level = 0`; `placement.py:150/206`,
    `incubator.py:252` and `repair.py:130` all take theirs from
    `node_centroids`, which selects `WHERE level = 0`. **No production path can
    call the members-based refresh on a level >= 1 node.**
  Good instinct by qa to chase the anomaly instead of dismissing it — that is
  how the real leaf defect surfaced. The upper-level inference just went one
  step too far, and the correction belongs on the ticket before anyone builds
  against it.

  **Rulings:**
  1. **#120 promoted to `todo` at `high`, and re-scoped to the leaf half.** Not
     backlog. The severity argument is not the LLM spend, it is that this breaks
     **#064's brief-freshness invariant in BOTH directions**: a signature that
     no longer tracks its members can fire invalidation when nothing changed
     (needless regeneration) and fail to fire when something did (a brief that
     describes members its node no longer has — a wrong map, not just an
     expensive one). #064 and #068 are the mechanism that makes incremental
     update trustworthy, which is the product's differentiator, and you and I
     have both leaned on node-id reuse when judging incremental behaviour. It is
     also not theoretical: **2 of 6 leaf nodes drifted in a single normal run.**
     Scoped to the leaf half it is small.
     One thing I found that the ticket must carry: **a full rebuild does not
     heal this, it CONSUMES it.** `replace_tree` computes each label's signature
     from the new members and hands it to `_reconcile`, which matches labels to
     existing nodes BY STORED SIGNATURE. A drifted node describes a member set
     that no longer exists, so it will usually fail to match — minting a new id
     and regenerating the brief — and in the unlucky case matches the wrong
     label and hands over the wrong brief. So #120 needs either a one-time
     reconciliation of stored signatures or an explicit statement that existing
     databases must be rebuilt from scratch.
  2. **Answered above: no production path reaches it, so the upper half is
     neither a defect nor latent.** Recorded on #120 with the evidence so it is
     removed from scope rather than left as a doubt.
  3. **Re-run consequence CONFIRMED, and narrowed.** qa said the first
     membership write to nodes 3, 4 **or 7** would refresh the signature and
     trigger a #064 re-brief. It is **nodes 3 and 4 only** — node 7 is level 1,
     its stored signature is already correct, and no members-based refresh can
     reach it. So: expect up to **two** unexpected brief regenerations on the
     next incremental pass, not three. Recorded on the re-run baseline so it is
     predicted rather than discovered.
