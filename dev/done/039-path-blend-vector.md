---
id: 039
title: Path-blend clustering vector (alpha concat of content + path) (T17)
priority: high
size: medium
depends_on: [035]
spec_refs: [build-order.md#T17, how-hrono-works.md, design-sketch-v1.md, clustering-lifecycle.md]
---

## Context
A section's clustering vector blends *what it says* with *where it lives*: raw
content similarity alone clusters unrelated files that happen to share vocabulary,
so the file path is folded in. This produces the combined vector that #T18's
UMAP/HDBSCAN clusters. It builds directly on #035's embeddings (content vectors)
and reuses #035's embed runner to embed the path with the same model.

## Description
Produce, for each section, a **combined vector** that blends its content vector
with its file-path vector so that the dot product of two combined vectors equals
`(1-alpha)*content_similarity + alpha*path_similarity` with `alpha = 0.5` (a baked
constant). Per how-hrono-works.md, concatenate the scaled vectors:

    combined = [ sqrt(1-alpha) * content_vec , sqrt(alpha) * path_vec ]

so a plain dot product recovers the blended similarity - path-aware similarity
that works unchanged with standard UMAP/ANN tooling.

- **Path vector**: embed the section's file path string with the SAME embedding
  model as the content (reuse #035's runner/store; embed-once keyed like content,
  e.g. by the path string's hash + model). A section's path is its
  repo-relative path (from the address); pick and document the exact string
  embedded (e.g. the path with separators, maybe the URI path segment).
- **Blend**: a pure function `combine(content_vec, path_vec, alpha=0.5)` doing
  the scale + concat above; L2-normalize the content and path vectors first if
  the model's vectors are not already unit-norm, so the similarity identity
  holds (state the assumption).
- The combined vector is what #T18 clusters. Decide and document whether it is
  stored (e.g. a combined-vector store keyed by section) or computed on the fly
  at cluster time from the two stored vectors - either is fine; on-the-fly keeps
  storage lean, storing avoids recompute. `alpha` is a baked constant (0.5), not
  config.

## Acceptance criteria
- [ ] For two sections, `dot(combine(c1,p1), combine(c2,p2))` equals
      `(1-alpha)*dot(c1,c2) + alpha*dot(p1,p2)` (within float tolerance) with
      alpha=0.5 - the blend identity holds.
- [ ] Path vectors are produced by embedding the path string with the SAME model
      as content, embed-once (a repeated path+model does not re-embed).
- [ ] The combined vector has the expected dimensionality (2x the model dims, or
      the documented shape) and is deterministic for the same inputs.
- [ ] `alpha` is a baked constant (0.5); changing content vs path weight is not a
      config knob.
- [ ] Regression-grade tests (offline, fake/fixed vectors): the blend identity,
      path embed-once, normalization assumption, and combined dims; a test fails
      if the identity breaks or alpha drifts.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- UMAP / HDBSCAN / cluster persistence (#T18 / #040).
- Upper-level (brief) vectors - topics have no file path, so briefs are embedded
  content-only (M4); this ticket is the section-level path blend.
- Recall-time path blending (same alpha, but that is the recall engine, M5).

## Review log
- 2026-08-16 PO: authored as T17 on the #035 embed runner/store. The scaled-
  concat form (sqrt weights) is the key trick so standard cosine tooling recovers
  the blended similarity. alpha=0.5 baked. Flagged the normalization assumption
  and the store-vs-compute-on-the-fly choice as dev's call.

## dev — 2026-08-16

Added `src/hrono/cluster/blend.py` (opens the cluster package). Pure Python (no
numpy — #040 pulls it with UMAP/HDBSCAN):

- `ALPHA = 0.5` baked. `combine(content_vec, path_vec, alpha=ALPHA)` L2-normalises
  both components then returns `[sqrt(1-ALPHA)*content_unit ; sqrt(ALPHA)*
  path_unit]`, so `dot(combine(c1,p1), combine(c2,p2)) == (1-ALPHA)*dot(c1,c2) +
  ALPHA*dot(p1,p2)` for unit inputs (verified to float tolerance). Combined dims =
  2 x model dims; deterministic; zero-norm guarded.
- Path is embedded with the SAME model as content, embed-once, by reusing #035
  wholesale: `register_path_bodies` stores each distinct path STRING (its
  repo-relative path, UTF-8 — the documented embedded string) as a content body
  keyed by its hash, so the existing `contents` + embed op + embeddings store
  vectorise it exactly once (and the embeddings FK to `contents` stays satisfied —
  the reason paths go through `contents` rather than a parallel table).
- `combined_vector(conn, content_digest, path, model)` computes the blend ON THE
  FLY from the two stored component vectors (storage stays lean); returns None if
  either component is not embedded yet.

Normalization assumption stated: stored component vectors are treated as
non-unit and normalised in `combine`, so the similarity identity holds regardless
of whether the model emits unit vectors.

Verified: blend identity holds for unit and non-unit (normalised) inputs; combined
dims = 2x; path embed-once flows through the real embed store (dup path -> one
content row -> one path vector, re-embed idempotent); combined_vector blends
stored components and is None when a component is missing. Tests offline with a
fake encoder. Gate clean: ruff, pytest 368.

Decisions flagged for review (both PO-noted as dev's call): (1) path vectors live
in the shared `contents`/`embeddings` store keyed by the path-string hash (reuse,
FK-clean) rather than a parallel path table; (2) combined vector computed on the
fly, not stored.

Out of scope (their tickets): UMAP/HDBSCAN/persist (#040), brief/content-only
upper-level vectors (M4), recall-time blending (M5). Commit 16e1992.

## qa — 2026-08-16 — PASS -> po-review

Re-ran the gate MYSELF: `ruff format --check` + `ruff check` clean, `pytest` 368
passed. Then drove the blend math and the real embed-once path, not on dev's
word:

- Blend identity: over 200 random NON-UNIT pairs, `dot(combine(c1,p1),
  combine(c2,p2))` vs `(1-a)*dot(unit(c1),unit(c2)) + a*dot(unit(p1),unit(p2))`
  max error 2.22e-16 (float epsilon). Holds for unit inputs too, and TRACKS the
  alpha passed at 0/0.25/0.75/1.0 (not silently 0.5). ALPHA=0.5 baked; combine's
  alpha param is test-only, the pipeline (`combined_vector`) always uses ALPHA.
- Combined dims = 2x model dims; deterministic; zero-norm component guarded (no
  NaN).
- Real embed-once path (fake encoder, real store + embed op): `register_path_
  bodies(["src/app.py","src/app.py","src/util.py"])` -> ONE content row for the
  dup, 3 distinct rows total (content + 2 unique paths); the embed op vectorises
  all 3 under the SAME model -> 3 vectors; re-embed idempotent. Paths key by
  `content_hash(path_body(path))` = the repo-relative path UTF-8 (the documented
  embedded string).
- `combined_vector` returns None when either component is unembedded (before
  embed, and for an unregistered path), and once both exist equals the on-the-fly
  `combine(stored_content_vec, stored_path_vec)` exactly, dims 8.

Code review: pure Python (numpy deferred to #040), L2-normalises both components
so the cosine identity holds regardless of model unit-norm (the stated
assumption, verified). Paths reuse the shared `contents`/`embeddings` store
(FK-clean, embed-once) — a path string only ever collides with content bytes if
they are byte-identical, which is content-addressing working as intended (benign).
One atomic Conventional Commit (16e1992). All ACs met.

Two decisions flagged by dev for PO (both PO-noted as dev's call, both sound —
not blockers): (1) path vectors live in the shared contents/embeddings store
keyed by the path-string hash rather than a parallel path table; (2) combined
vector computed on the fly, not stored. Storage stays lean and #040 can decide to
materialise if profiling wants it.
- 2026-08-17 PO: PASS -> done. Independently verified the load-bearing blend
  identity: over 500 random NON-UNIT pairs, dot(combine(c1,p1), combine(c2,p2))
  vs (1-a)*dot(unit(c1),unit(c2)) + a*dot(unit(p1),unit(p2)) max error 1.11e-16
  (float epsilon). Combined dims = 2x model dims; alpha correctly weights content
  vs path (orthogonal-content/parallel-path -> blended dot == alpha exactly at
  0/0.5/1.0); zero-norm guarded (no NaN); ALPHA=0.5 baked (combine's alpha param
  is test-only, the pipeline `combined_vector` always uses ALPHA). Gate: ruff
  clean, pytest 368 passed. RATIFIED both flagged decisions (both sound, not
  defects): (1) path strings vectorise through the shared content-addressed
  contents/embeddings store keyed by the path hash (FK-clean, embed-once; a path
  only shares a row with content if byte-identical - content-addressing working
  as intended); (2) combined vector computed on the fly, not stored (storage
  lean; #040 may materialise if profiling wants). Unblocks #040 (cluster build).
  Closed at 16e1992.
