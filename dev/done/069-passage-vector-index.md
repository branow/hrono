---
id: 069
title: passage vector index — embed passages (content + path) for the recall vector leg (T25.1)
priority: high
size: medium
depends_on: [032, 035, 039]
spec_refs: [build-order.md#T25.1, how-hrono-works.md, design-sketch-v1.md]
---

## Context
Recall's vector leg ranks PASSAGES (~800 B, the injection unit), not sections
(~10 KB, the clustering unit). So the passage store needs its own vectors:
each passage's content vector AND its path vector, so recall can score by the
same path-blended similarity used for clustering — `(1-a)*sim(q,content) +
a*sim(q,path)`, a=0.5 (#039). This ticket makes passages embeddable and indexed;
the leg logic that queries them is #072.

## Description
- Embed each stored passage's body and its path into the embed store (#035),
  content-hash keyed so a passage shared by content embeds once (like sections).
  Passages already carry a content hash and sp_paths (#031/#032); reuse the same
  embed op + path-blend (#039), just over passages.
- Confirm/extend the embed op's scope so passages are vectorised (today it may
  cover sections/section-content only) — an unembedded passage cannot be recalled.
- Keep the blend identity from #039 (a=0.5 baked); the combined passage vector is
  computed the same way the clustering vector is.
- Incremental: an unchanged passage (same content hash) is never re-embedded.

## Acceptance criteria
- [ ] Every stored passage has a content vector and a path vector in the embed
      store, content-hash keyed (embed-once; a re-run embeds nothing unchanged).
- [ ] The path-blended passage vector matches #039's identity (a=0.5), verifiable
      to float epsilon.
- [ ] Passages of both granularities coexist with section vectors without
      collision (content-hash keys are global).
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The vector leg query + z-floor (#072) and FTS5 keyword index (#070).
- Brief passages / `node://` (#071) — this is source passages first.
- Any recall endpoint (#075).

## Review log
- 2026-08-24 PO: authored as T25.1, M5 kickoff. Passages need their own path-
  blended vectors (reuse #035 embed + #039 blend) so the vector leg (#072) can
  rank them. Baked a=0.5. Incremental via content-hash like every embed.
- 2026-08-24 dev: DONE, committed fa81882, handoff to qa. NO production change
  needed — passages are ALREADY embeddable + path-blended by the existing ops:
  split's `_store_body` upserts each passage body into `contents` (like sections),
  so the #035 embed op (embeds every content row) already vectorises passage
  bodies; `register_path_bodies` (#040) already embeds the file path passages
  share; and #039 `combined_vector(content_hash, path, model)` already produces
  the a=0.5 path-blended passage vector. The embed op's scope already covers
  passages (it selects from all of `contents`), so nothing to extend.
  Locked it in with regression tests over the real sync->split->embed path
  (tests/embed/test_passage_vectors.py): every passage has a content vector AND a
  path vector; the combined vector equals #039's blend and is 2x dims; re-embed is
  a no-op (embed-once by content hash); a section and its lone passage sharing
  bytes share one vector (global keys, no collision). Verified: ruff clean; pytest
  470 passed / 1 skip (+5). #072 (vector leg) can call blend.combined_vector over
  passages directly.
- 2026-08-24 qa: PASS (commit fa81882) -> po-review. Tree CLEAN at handoff. I
  independently verified the "no production change needed" claim rather than trust
  it: `embed/store.missing` selects from ALL of `contents` (WHERE NOT EXISTS an
  embedding — not section-scoped), and `split_op._store_body` upserts passage
  bodies into `contents` (line 86, same path as sections line 75), so passage
  bodies ARE already embedded; `register_path_bodies` embeds the shared file path.
  The property genuinely emerges from #032 + #035 + #039 — adding redundant
  production code would violate "minimum code, nothing speculative", so locking it
  in with regression tests is the correct deliverable and the `test:` commit type
  is honest.
  - Tests drive the REAL sync->split->embed path over a real git repo (fake
    encoder only): every passage has a content vector AND a path vector; the
    combined vector == `combine(content, path)` (#039 blend, a=0.5) and is 2x dims;
    re-embed is a no-op (embed-once by content hash); a section and its lone
    passage sharing bytes share one vector (global content-hash keys, no
    collision). These would FAIL if a future change stopped indexing passages.
  - ruff clean; full suite 470 passed / 1 skip; atomic `test:` Conventional Commit.
  M5 (Recall) vector-leg substrate is in place for #072. (Pre-existing unrelated
  `.gitignore` edit remains uncommitted.)
- 2026-08-24 PO review: PASS -> done. Independently verified the "no production
  change needed" claim rather than trusting it: `embed/store.missing` is
  `SELECT c.content_hash FROM contents c WHERE NOT EXISTS(...)` — ALL contents,
  not section-scoped; `split_op._store_body` stores passage bodies into `contents`
  (line 87) the same way as sections (line 76). So passages are already embedded
  (#035), paths by register_path_bodies, blended by #039 (a=0.5) — the property
  genuinely emerges from #032+#035+#039. Adding redundant production code would
  violate "minimum code, nothing speculative", so a `test:` commit locking it in
  is the correct deliverable. Gated #069's commit (fa81882) in an isolated
  worktree (tree carried untracked #070/recall WIP): ruff clean, embed suite 19
  passed / 1 skip incl. the 5 new passage-vector tests. All acceptance criteria
  met (content + path vectors per passage, blend == #039, embed-once, no
  section/passage key collision). Closed. #072 (vector leg) can call
  blend.combined_vector over passages directly.
