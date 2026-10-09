---
id: 075
title: `recall` endpoint + CLI + calibration test (T28)
priority: high
size: big
depends_on: [074, 071, 010]
spec_refs: [build-order.md#T28, implementation-notes.md, how-hrono-works.md]
---

## Context
T28 wires the recall engine (#072-074 over #069-071) into the ONE synchronous,
fast endpoint (implementation-notes: "recall is the one fast synchronous
endpoint"; the engine is the frozen recipe and none of it leaks into the API).
This is the read door into the tree and the last piece before M6 export = MVP.

## Description
- `POST /trees/<name>/recall  { "question": "...", "limit": 10 }` (limit optional,
  default 10, capped by the recipe's 10). **reader** role (recall is a GET-class
  read). Synchronous — runs the engine inline, not a job.
- Run the engine over the UNION of source and brief passages (#071): vector leg
  (#072) + keyword leg (#073) -> RRF fusion (#074) -> up to `limit` hits.
- Response shape (implementation-notes):
  `{ "hits": [ { "uri": "...", "kind": "summary|source", "header": "...",
  "body": "...passage...", "score": 0.87 } ], "message": null }`. Each hit is its
  one-line header (address + `sp:` structure paths) + the full passage body,
  tagged summary vs source (#071 origin). Empty hits -> `message` = "no confident
  matches - explore the map." (hits []).
- CLI: `hrono recall <tree> "<question>" [--limit 10]` (thin #010 client of the
  endpoint). Follow the settled `tree`-family grammar decision (verb-first;
  `recall` is its own top-level command per implementation-notes `hrono recall
  <tree> "<q>"`).
- CALIBRATION TEST (the point of T28): on a planted corpus, a question whose
  answer is a known passage recovers THAT passage above the z-floors and through
  fusion; a question with no confident answer returns the explore message (strict-
  miss fails safe to explore, never to a bad hit). Assert both the recall AND the
  strict-miss, so a future recipe drift that loosens or breaks the floors fails.
- CORPUS SIZING (from #072/#073 reviews): both legs z-score over their own
  distribution, so tiny corpora cannot fire them. Vector leg: max z ~sqrt(N-1),
  so a corpus under ~13 passages never produces a vector hit. Keyword leg
  (z>=6.0): needs a matched set of ~37+ to reach the floor (very conservative by
  design, never alone). So: (1) size the calibration corpus to >= ~13 passages so
  the vector-leg recovery path is exercised through the endpoint; (2) do NOT try
  to fire the keyword leg through a small end-to-end corpus — its
  qualification/never-alone logic is already unit-tested in #073; exercise it at
  the endpoint only with a corpus large enough (~37+ matches), else assert it
  correctly contributes nothing; (3) always cover the strict-miss ->
  empty->explore path. Do not write a calibration that silently tests neither leg.

## Acceptance criteria
- [ ] `POST /trees/<name>/recall` returns JSON hits (snake_case keys) ranked by
      the engine; reader role can call it; unauthenticated is rejected.
- [ ] Each hit carries uri, kind (summary|source), header (address + sp: paths),
      body, score; brief and source passages both appear in the union.
- [ ] An empty union returns hits [] + the exact explore message.
- [ ] `hrono recall <tree> "<q>" [--limit N]` prints the hits via the #010 client.
- [ ] Calibration: a planted-answer question recovers the right passage; a no-
      answer question returns the explore message. Regression-grade (breaks if the
      z-floors / fusion drift).
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Export / explore rendering (M6).
- ANN/speed optimization; streaming; pagination.
- Any recipe knob in the API — the recipe is frozen and internal.

## Review log
- 2026-08-24 PO: authored as T28, the synchronous read door. reader-role
  endpoint + `hrono recall` CLI over the frozen engine; the load-bearing
  deliverable is the CALIBRATION test (planted-answer recovers; strict-miss ->
  explore message) so recipe drift is caught. Closes M5; M6 export = MVP next.
- 2026-08-25 dev: DONE, committed 8267b21, handoff to qa. Wired the frozen engine
  into the read door:
  - `recall/engine.py` `recall(conn, question, model, encode, limit)`: embeds the
    query, runs vector leg (#072) + keyword leg (#073) over source+brief passages,
    fuses (#074), renders <=limit (capped 10) Hits (uri, kind summary|source,
    header = address + sp: paths, body, fused score); empty -> explore message.
    Encoder injected (testable offline). Added `fusion.Fusion.ranked` (id,score)
    for scoring, keeping `.hits` (074 tests unchanged).
  - `POST /trees/{name}/recall` (reader, synchronous): resolves the embedding
    model, builds the query encoder OFF the #008 lock, runs the engine, returns
    `{hits:[{uri,kind,header,body,score}], message}`. `_query_encode` is the
    test seam.
  - `hrono recall <tree> "<q>" [--limit]` top-level CLI (verb-first, per
    implementation-notes) over the #010 client; prints hits or the explore line.
  - CALIBRATION (load-bearing): planted-answer question recovers THAT passage
    above the floors through fusion; no-answer -> explore; TINY corpus (<13)
    fails safe to explore (vector leg's max z ~ sqrt(N-1) unreachable) — covers
    both the vector-recovery and keyword-only/strict-miss regimes per the #072
    sizing note.
  Verified: ruff clean; pytest 505 passed / 1 skip (+18 across engine calibration,
  endpoint role/shape/explore, CLI). Drove the real `hrono recall` CLI (help +
  usage). Real-model query embedding is the flagged manual step (no creds in dev).
  **M5 (Recall) COMPLETE (069-075).** Next: M6 export = MVP.
- 2026-08-25 qa: PASS (commit 8267b21) -> po-review. Tree CLEAN at handoff.
  Verified the M5 capstone on every dimension:
  - Calibration (the load-bearing deliverable) drives the REAL engine end-to-end:
    a planted-answer question over a >=14-passage corpus recovers THAT passage
    (hits[0].uri == answer, kind == source) through the full vector-leg -> fusion
    path; a no-answer question returns hits () + the exact explore message; and a
    tiny (<13) corpus fails safe to explore (vector max z ~sqrt(N-1) unreachable),
    never a low-confidence hit. Regression-grade — recipe/z-floor drift breaks it.
  - Endpoint: `POST /trees/{name}/recall` is reader-role (unauth -> 401), returns
    `{hits:[{uri,kind,header,body,score}], message}` (snake_case, exact shape via
    asdict), kind = summary|source from #071 origin, empty -> [] + exact explore
    message. The embedding model is resolved + the encoder built OFF the #008 lock,
    then the engine runs; `_query_encode` is the test seam.
  - CLI: smoke-drove `hrono recall {tree} {question} [--limit 10]` — verb-first
    per implementation-notes, registered top-level, over the #010 profile client.
  - Fusion refactor is backward-compatible: `Fusion.ranked` (id, score) added for
    scored rendering, `.hits` kept as a derived property, so #074's tests are
    unchanged (all green in the 505).
  - Security: reader enforced server-side (recall is a read); no secret in the
    recall path (query embedding is the local model). ruff clean; full suite 505
    passed / 1 skip; atomic Conventional Commit.
  Non-blocking note for PO / future ANN work (#035 vec0 shadow index): the engine
  scans every passage and computes combined vectors INSIDE the DB connection, so a
  recall holds the connection for an O(N-passages) scan — fine for MVP corpora and
  the correctness-first frozen recipe, but recall latency (and any serialization
  against the single writer) grows with corpus size; the deferred ANN index is the
  place to address it. Real-model query embedding is the flagged manual qa step
  (no creds in dev). **M5 (Recall) COMPLETE — the tree now has its read door.**
  (Pre-existing unrelated `.gitignore` edit remains uncommitted.)
- 2026-08-25 PO review: PASS -> done. Tree clean, #075's commit is HEAD (8267b21).
  Read engine.py: embeds the query, filters z>=3.5 from vector_leg.scores() for the
  vector hits, runs the keyword leg with the vector-z support map, fuses (#074),
  renders Hits (uri, kind=summary for `node` else source, header=uri + sp: paths,
  body, fused score), empty union -> explore message; cap=min(limit, 10); encoder
  injected. Ran the calibration/endpoint/CLI tests (35 pass), ruff clean, full
  suite 505 passed / 1 skip. The load-bearing CALIBRATION is regression-grade:
  planted-answer recovers THAT passage through vector->fusion on a >=14-passage
  corpus, no-answer -> exact explore message, tiny (<13) corpus fails safe to
  explore (my #072/#073 sizing note honored). Endpoint reader-role (401 unauth),
  exact snake_case shape; CLI verb-first per the settled grammar; no secret in the
  recall path. All acceptance criteria met. Closed. Authored #077 (backlog) for
  qa's O(N)-scan note: recall computes combined vectors for EVERY passage inside
  the DB connection, so latency + single-writer contention grow with corpus — the
  deferred vec0/ANN shadow index (#035 note) is the fix. **M5 (Recall) COMPLETE
  (069-075); the read door works. Next: M6 Export = MVP.**
