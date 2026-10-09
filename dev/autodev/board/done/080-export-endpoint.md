---
id: 080
title: `GET /trees/<name>/export?levels=N` endpoint — return the rendered agent-facing tree (T31)
priority: high
size: medium
depends_on: [078, 079]
spec_refs: [build-order.md#T31, implementation-notes.md]
---

## Context
T31 exposes the export render (#078 collapse + #079 MD) over HTTP. Export is a
read (implementation-notes: `GET /trees/<name>/export?levels=N`, reader-class).
v1 returns the whole rendered tree in one response body; partial/streamed
download is deferred.

## Description
- `GET /trees/<name>/export?levels=N` (reader role; `levels` optional, default the
  export target 3-4). Runs #078 collapse -> #079 render and returns the rendered
  agent-facing tree. NOTE (from #078): `collapse` floors `levels` at 2 (an export
  needs at least a root + a leaf level), so `levels=1/0/negative` yield a 2-level
  export, not an error — surface this consistently (document the floor; a
  non-integer `levels` query param is still a clean 400/422, not a 500).
- PAYLOAD SHAPE — OPEN QUESTION for dev (implementation-notes says "one MD
  document in the response body" but the CLI #081 must write a FOLDER/FILE TREE):
  reconcile these. RECOMMENDED: return a path->content manifest (JSON:
  `{ "files": [ { "path": "root.md", "content": "..." }, ... ] }`) — it IS one
  response body and #081 materializes the folder tree cleanly from it. If the
  literal "one MD document" is preferred, concatenate with unambiguous file-
  boundary markers #081 can split. Pick one, document it, keep #081 in lockstep.
- Read-only over the stored tree; no job (synchronous like recall). Unknown tree
  or unbuilt tree -> a clean domain error (not a crash / not an empty 200 that
  looks built).

## Acceptance criteria
- [ ] `GET /trees/<name>/export?levels=N` returns the rendered agent-facing tree
      (per the chosen payload shape); reader role; unauthenticated rejected.
- [ ] `levels` controls the collapse depth (#078); default applied when omitted.
- [ ] An unknown / not-yet-built tree returns a clear error, not a misleading
      empty success.
- [ ] The payload shape is documented and #081 consumes it directly.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The collapse (#078) and render (#079) internals.
- Disk materialization / CLI (#081).
- Streamed / partial export delivery (deferred, implementation-notes).

## Review log
- 2026-08-25 PO: authored as T31. Reader-role synchronous GET over #078+#079.
  Flagged the payload-shape reconciliation (spec's "one MD body" vs #081's folder
  tree) with a JSON path->content manifest recommendation; keep #081 in lockstep.
- 2026-08-25 dev: DONE, committed b629faf, handoff to qa. `GET /trees/{name}/
  export?levels=N` (reader, synchronous): loads the StoredTree (export.store.load),
  runs #078 collapse + #079 render, returns the RESOLVED payload-shape open
  question as a JSON path->content MANIFEST — `{"files":[{"path","content"},...]}`
  (one response body AND #081 materialises the folder tree directly from it).
  `levels` default 4; #078 floors it at 2 so levels<2 yields a 2-level export (not
  an error); a non-integer levels is a clean 422 (FastAPI); an unbuilt tree is a
  clean 404 (NotFound), never a misleading empty 200.
  Verified: ruff clean; pytest 524 passed / 1 skip (+5: unauth 401, reader gets
  the manifest with root.md + child briefs, unbuilt->404, levels=1->200 floored,
  non-int levels->422). #081 consumes `files[].path/content` directly.
- 2026-08-25 qa: PASS (commit b629faf) -> po-review, with a HIGH-priority finding
  filed for the PO (#082, below). 080 meets all its own criteria:
  - `GET /trees/{name}/export?levels=N` is reader-role (unauth -> 401), loads the
    StoredTree, runs #078 collapse + #079 render, and returns the JSON path->content
    manifest `{"files":[{"path","content"},...]}` sorted by path — the resolved
    payload-shape open question (one body AND #081 materialises the folder tree).
  - `store.load` returns None when the tree has zero nodes -> clean 404 `NotFound`
    (never a misleading empty 200); non-integer `levels` -> clean 422 (FastAPI);
    `levels<2` -> 200 floored to a 2-level export (my #078 clamp, validated at the
    boundary here). All 5 endpoint tests cover these.
  - Isolated the commit in a worktree at b629faf (a concurrent #081 CLI WIP was
    churning `commands.py` and briefly made a bare `ruff check` red): the 080
    commit is ruff-clean, full suite 524 passed / 1 skip.
  FINDING for PO (out of 080's scope -> filed as backlog #082, NOT a block on 080):
  the export pipeline (store.load -> #078 collapse -> #079 render) assumes a SINGLE
  root, but #062 can terminate with MULTIPLE top-level nodes (its non-reducing-drop
  guard). I reproduced that `store.load` then picks one top node via
  `max(node_level, key=level)` and the OTHER top node + its subtree become
  UNREACHABLE from root.md (rendered at a malformed `"/brief.md"` path). This
  silently drops part of the exported tree for multi-root corpora (the common
  single-root case is fine). It lives in the #078/#079 internals that 080 wires —
  explicitly out of 080's scope ("out of scope: the collapse/render internals") —
  so 080 passes, but #082 is HIGH priority and should be resolved before/with the
  #081 MVP close so the MVP export never silently omits topics. (Pre-existing
  `.gitignore` edit still uncommitted; the concurrent #081 WIP is separate.)
- 2026-08-25 PO review: PASS -> done. Gated #080's commit (b629faf, one below HEAD
  since #081 is committed on top) in an isolated worktree: ruff clean, 19
  export/endpoint tests pass. The endpoint is correct — reader role (401 unauth),
  loads StoredTree -> #078 collapse -> #079 render, returns the JSON path->content
  MANIFEST `{"files":[{path,content},...]}` sorted by path. This RESOLVED the
  payload-shape open question exactly as I recommended (one response body AND #081
  materialises the folder tree directly). levels default 4, floored at 2 (my #078
  clamp, boundary-tested here), non-integer levels -> clean 422, unbuilt tree ->
  clean 404 (never a misleading empty 200). All acceptance criteria met. Closed.
  qa's multi-root finding is correctly OUT of #080's scope (collapse/render
  internals) — I decided it (option b, single-root build guarantee in #062) and
  promoted #082 to todo at high priority; the MVP is not complete until #081 AND
  #082 land.
