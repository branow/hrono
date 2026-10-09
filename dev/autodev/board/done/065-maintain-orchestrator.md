---
id: 065
title: `maintain` orchestrator — the easy button that runs all ops in order to root (T24)
priority: high
size: big
depends_on: [059, 062, 064, 032, 035, 040]
spec_refs: [build-order.md#T24, implementation-notes.md, how-hrono-works.md]
---

## Context
T24, the easy button (implementation-notes: `POST /trees/<name>/maintain ->
{job_id}` and `hrono tree <name> maintain`). One command runs the whole pipeline
in dependency order, recursing to root: sync -> split -> embed -> cluster ->
brief -> (embed briefs -> cluster -> brief-upper) x levels -> root. It is the
end-to-end drive that makes M4 real and is the last piece before M6 export
(MVP). It orchestrates existing ops; it must not reimplement them.

## Description
A `maintain` op + its endpoint/CLI that runs the ordered pipeline over a tree,
doing only the work that is stale/missing (never a blind full rebuild):
- Order: `sync` (#025) -> `split` (#032) -> `embed` (#035) -> `cluster` (#040)
  -> `brief` (#059) -> recursion-to-root (#062: embed+cluster briefs #060 ->
  brief-upper #061 per level) until root.
- **Incremental by construction**: each stage already skips unchanged inputs
  (content-hash caches #035/#058, brief signatures #064), so a `maintain` on an
  unchanged tree does near-zero work. Verify this end-to-end — it is the
  differentiator, not a nice-to-have.
- Wire `POST /trees/<name>/maintain -> {job_id}` (writer role) and
  `hrono tree <name> maintain` (prints the job id). The job fans out per stage/
  item using the existing #023/#024 framework; a stage failure isolates per the
  jobs model and leaves the rest pending.
- OPEN QUESTION for dev: does `maintain` model stages as an ordered chain of
  child jobs (a stage starts when the prior completes) on today's two-level
  fan-out, or does it need the #051 job-DAG design first? Recommended: implement
  ordered stages on the CURRENT framework (sequential stage dispatch), and if a
  real dependency-graph need appears, note it against #051 — do NOT block T24 on
  the #051 design. Confirm the sequencing approach before building.

## Acceptance criteria
- [ ] `POST /trees/<name>/maintain` and `hrono tree <name> maintain` kick a job
      that runs sync->split->embed->cluster->brief->recurse-to-root in order.
- [ ] On a fresh tree it builds the whole tree to a single root, end to end.
      Automated gate uses fakes (fake embedder + fake LLM client, as the M4 op
      tests already do). Driving it against a REAL embedding model + LLM API key +
      a source repo is a MANUAL qa/stakeholder verification step (the dev env
      lacks credentials) — call it out, do not block the gate on it.
- [ ] On an unchanged tree, a second `maintain` re-condenses and re-embeds
      NOTHING (content-hash caches from #058/#035 survive) — assert this real
      partial skip. KNOWN M4 LIMITATION to state plainly, not hide: `cluster`
      (`replace_tree`) deletes+recreates nodes with fresh ids every run, and
      `briefs.node_id ON DELETE CASCADE` wipes the briefs, so the cluster + brief +
      brief-upper layers FULLY re-run each maintain. The "near-zero second run" at
      the brief layer needs STABLE cluster node ids across rebuilds = incremental
      placement, which is M7 (#T33-T39) — see #068. Do NOT build that here.
- [ ] writer role required; stage failures isolate; job id returned and
      trackable. `ruff format`, `ruff check --fix`, `pytest` clean; committed.

## Out of scope
- The `propagate` judge cascade and settle/incubator (M7).
- Incremental placement (a changed file re-touching ONLY its path, no global
  re-cluster) and upward propagation of a changed leaf brief to upper levels
  (build-tree currently no-ops once built) — both are M7 (T33-T39). M4 maintain
  does full-build + per-stage content-hash/signature SKIPS only.
- Export rendering (M6 / T29+).
- A general job-DAG engine (#051 design) — sequence stages on the current
  framework; only escalate to #051 if a real need is proven.

## Review log
- 2026-08-24 PO (during #062 review): corrected scope. The original "one changed
  file touches only its path" criterion is M7 (incremental placement + upward
  propagation), NOT M4 — #062 review confirmed build-tree no-ops once built and a
  changed leaf brief does not propagate upward yet. Softened that criterion to the
  M4-real per-stage-skip savings (condense/embed skip unchanged content; brief
  skips unchanged-signature nodes) and added the M7 deferral to Out of scope, so
  this in-progress ticket is not mis-scoped toward an M7 feature.
- 2026-08-23 PO: authored as T24, the end-to-end easy button over existing ops.
  Ordered stages to root; the load-bearing acceptance criterion is "second
  maintain on an unchanged tree does near-zero work" (the differentiator). Flagged
  the stage-sequencing vs
  #051-DAG question with a "sequence on the current framework, don't block on
  #051" default.
- 2026-08-24 PO: RESOLVED the design conflict dev raised (option a). Dev is
  correct: with `cluster` deleting+recreating nodes with fresh ids and
  `briefs.node_id ON DELETE CASCADE`, the brief layer cannot be near-zero on a
  second run — that needs stable node ids = M7 incremental placement. The
  "near-zero second run" was my over-scoped criterion (an M7 promise on an M4
  ticket). Re-scoped 065 to the M4 FULL-BUILD easy-button: keep fresh-tree->root
  end-to-end + the REAL condense/embed content-hash skip; state the cluster/brief
  full-rebuild as a known M4 limitation; make the real-model drive a manual qa
  step (dev env has no credentials). Spun off #068 (M7) for the stable-node-id /
  incremental-placement work that makes the brief layer incremental. 065 is now
  UNBLOCKED and ready — re-pick it. Everything else in M4 (057-064, 066) is done.
- 2026-08-24 dev: STOP -> back to todo (design conflict for PO to resolve; not an
  implementation defect). The op orchestration (sync->split->embed->cluster->
  brief->build-tree in order) + a POST /trees/{name}/maintain endpoint + a
  `hrono tree ... maintain` CLI are all straightforward to build on the current
  framework (sequential stage dispatch, per the flagged sequencing default — no
  #051 DAG needed). BUT the load-bearing acceptance — "a second maintain on an
  unchanged tree does near-zero work" and "a single changed file touches only its
  path" — is NOT achievable with today's ops:
    - #040 `cluster` full-rebuilds via `replace_tree`, which DELETEs level-0 nodes
      and INSERTs fresh ones with new autoincrement ids every run.
    - `briefs` FK `node_id ... ON DELETE CASCADE`, so re-clustering cascade-
      deletes ALL level-0 briefs; `brief.stale_or_missing` then sees new node ids
      with no brief and REGENERATES every brief (the expensive LLM reduce). Same
      cascade wipes the upper tree.
    - Condensations survive (content-hash keyed) so condense is near-zero, but the
      brief/brief-upper layers are full-cost on every maintain.
  Root cause: briefs are keyed by an unstable cluster node id. "Near-zero second
  run" needs STABLE cluster node ids across rebuilds (incremental placement /
  sticky re-check), which is M7 (#T33-T39), explicitly out of M4 scope.
  Recommended PO resolutions (pick one): (a) re-scope 065 for M4 as a FULL-BUILD
  easy-button — drop the "near-zero second run" + "changed-file-only" criteria,
  keep "fresh tree builds to root end-to-end"; add them back in M7; or (b)
  sequence 065 after M7 incremental clustering. Also note: 065's "driven for real,
  observed working" needs a real embedding model + LLM API key + a source repo,
  which the dev environment lacks (a manual/qa verification step regardless).
  Everything else in M4 (057-064, 066) is committed and in qa/done.
- 2026-08-24 dev: DONE (re-scoped M4 full-build), committed 38ddc82, handoff to
  qa. Built the `maintain` easy-button end to end:
  - `hrono/tree/maintain.py` — the `maintain` op orchestrates the existing ops in
    order sync->split (per source) -> embed -> condense -> cluster -> brief ->
    build-tree (recurse to root). Sequential stages on the current jobs framework
    (no #051 DAG, per the confirmed default); a stage that raises fails the
    maintain leaf. Threads encoder_for/client/build seams so the gate drives the
    REAL op chain with a fake embedder + fake LLM; production passes none.
    (Included condense — the ticket's order line omitted it, but brief needs it.)
  - `server/trees.py` — `POST /trees/{name}/maintain` (writer role) enqueues a
    maintain job and returns {job_id}; wired into app.py + registered the op.
  - `hrono/tree/commands.py` — `hrono tree maintain <name>` POSTs via the profile
    client and prints the job id. (Typer puts the subcommand first, so it is
    `tree maintain <name>` not the spec's kubectl-style `tree <name> maintain`;
    the endpoint is canonical — noted for PO spec reconciliation.)
  - KNOWN M4 LIMITATION stated (not hidden): embed + condense skip on re-run
    (content-hash caches), but cluster/brief/brief-upper full-rebuild every run
    (fresh node ids + briefs.node_id CASCADE) — near-zero brief layer needs M7
    stable-id incremental placement (#068).
  Verified: ruff clean; pytest 465 passed / 1 skip (+11: end-to-end over a LOCAL
  git repo with fakes builds a fresh tree to a single root; second maintain
  re-embeds + re-condenses NOTHING; missing model fails cleanly; endpoint role
  matrix + job-id trackable; CLI posts + clean no-profile error). Drove the real
  `hrono tree maintain` CLI (help + no-profile error observed). Real-model /
  real-LLM end-to-end drive is the flagged manual qa step (no creds in dev env).
  **M4 (Brief) build pipeline COMPLETE** (057-066).
- 2026-08-24 qa: PASS (commit 38ddc82) -> po-review. Tree CLEAN at handoff.
  Verified every dimension of the re-scoped M4 easy-button:
  - End-to-end is genuine: the fresh-tree test runs the REAL maintain op over a
    REAL local git repo — real sync (git clone) + real split (tree-sitter ->
    sections), only the ML/LLM backends faked (encoder/client/build seams) exactly
    as the ticket allows. Asserts sections>=3, embeddings>0, condensations>=3,
    briefs>0, nodes recurse to a single root. Real-embedding/real-LLM drive is
    correctly a manual qa step (no creds in dev env).
  - Load-bearing M4-scoped skip verified: a second maintain on the unchanged tree
    re-embeds and re-condenses NOTHING (content-hash caches from #035/#058 hold).
    The KNOWN limitation — cluster/brief/brief-upper full-rebuild each run because
    `replace_tree` recreates nodes with fresh ids and `briefs.node_id ON DELETE
    CASCADE` wipes briefs — is stated plainly and correctly deferred to M7 (#068),
    not hidden.
  - Orchestration only, no reimplementation: sync->split (per source) -> embed->
    condense->cluster->brief->build-tree in dependency order on the current jobs
    framework (sequential, no premature #051 DAG); a stage raise fails the leaf.
    Good catch adding `condense` to the order (the ticket's line omitted it).
  - Endpoint + CLI: `POST /trees/{name}/maintain` enforces writer server-side
    (401 unauth / 403 reader / writer -> trackable job_id), returns only the job id
    (config-vs-work separated). I smoke-drove `hrono tree maintain <name>`: wired,
    clean no-profile error (pointing at `hrono profile add`, the #045 copy).
  - ruff clean; full suite 465 passed / 1 skip; commit atomic + Conventional.
  Process note (positive): dev correctly STOPPED on the scope conflict and
  escalated to the PO rather than build an M7 feature into M4; PO re-scoped + spun
  off #068. Non-blocking for PO: CLI is `tree maintain <name>` (Typer subcommand-
  first) vs spec's `tree <name> maintain` — dev flagged it; endpoint is canonical,
  reconcile the spec wording. **M4 (Brief) COMPLETE — a source now builds to a
  root tree.** (Pre-existing unrelated `.gitignore` edit remains uncommitted.)
- 2026-08-24 PO review: PASS -> done. Tree clean, #065's commit is HEAD (38ddc82).
  Read maintain.py + ran the gate independently: 9 tree/endpoint/CLI tests pass,
  ruff clean, full suite 465 passed / 1 skip. The re-scope holds exactly: the op
  orchestrates existing ops in dependency order (sync->split->embed->condense->
  cluster->brief->build-tree, sequential on the current framework, no premature
  #051 DAG), the endpoint enforces writer server-side and returns only a job id
  (config-vs-work separated), and the KNOWN M4 limitation (cluster/brief full-
  rebuild; only embed+condense skip on re-run) is stated in the module docstring
  and deferred to #068, not hidden. qa drove it end-to-end over a REAL local git
  repo to a single root with only the ML/LLM backends faked. All re-scoped
  acceptance criteria met. Closed.
  PO reconciliations: (1) my ticket's order line omitted `condense` — dev
  correctly inserted it before `cluster`/`brief` (brief needs condensations);
  acknowledged, my omission not a defect. (2) DECISION on the CLI grammar: accept
  the Typer-natural `hrono tree maintain <name>` over the spec's kubectl-style
  `hrono tree <name> maintain`. It is idiomatic (gh-style `<resource> <verb>
  <name>`), the endpoint `POST /trees/{name}/maintain` is canonical, and the whole
  `tree` command family (op, export) will follow the same grammar — so the M5/M6
  `tree op` and `tree export` tickets must use `tree <verb> <name>` too. Spec
  (implementation-notes.md) to be reconciled to this wording. **M4 (Brief)
  COMPLETE (057-066); a source now ingests, splits, embeds, condenses, clusters,
  briefs, and recurses to a single root via one `maintain` command.**
