# hrono — build order

Milestones -> tasks -> subtasks. Each task/subtask is one thing to implement and test. Top-level numbered T1..; fat tasks carry decimal subtasks. Per-type work (each source type, provider, model kind) is its own subtask. MVP at M6; M7 is the incremental lifecycle. API in `implementation-notes.md`.

## M0 — Skeleton
- **T1** SQLite connection + migration runner
- **T2** `hrono serve` HTTP skeleton + `/health` + `/version`
- **T3** Secrets at rest
  - T3.1 `keys` table + key_id/fingerprint model
  - T3.2 master-key startup load (file/env, refuse-without, fingerprint)
  - T3.3 encrypt/decrypt helper (Fernet) tagging key_id
- **T4** Auth
  - T4.1 `users` CRUD + token hashing
  - T4.2 Bearer middleware + role enforcement
  - T4.3 bootstrap admin token on empty user table
- **T5** CLI foundation
  - T5.1 CLI skeleton + command routing
  - T5.2 context store (`config.toml`: add/list/use/current/rm)
  - T5.3 HTTP client wrapper (Bearer header, error mapping)

## M1 — Registries
- **T6** Registry CRUD base (list/get/set/delete, secret masking, validation hook, shared-resource staleness propagation)
- **T7** `sources`
  - T7.1 source config model + CRUD
  - T7.2 git validation (reach + auth: none/token/ssh)
  - (each later source type brings its own validation: T41–T43)
- **T8** `connections`
  - T8.1 CRUD + secret encryption
  - T8.2 anthropic validation (list-models)
  - (other providers' validation ships with them: T44)
- **T9** `models`
  - T9.1 CRUD + `kind`
  - T9.2 embedding validation (load, emit vector of declared dims)
  - T9.3 text validation (round-trip via connection)
- **T10** `prompts`
  - T10.1 CRUD + role typing
  - T10.2 default seeding + prompt-hash link for invalidation

## M2 — Ingest
- **T11** Jobs framework
  - T11.1 job record schema + status model
  - T11.2 atomic leaf runner + worker loop
  - T11.3 scope resolver (all/source/section/node/level -> item set)
  - T11.4 op registry + dispatch
- **T12** `sync` op — git clone/pull to cache + version capture
- **T13** Filter — globs + size cap + null-byte sniff
- **T14** `split` op
  - T14.1 tree-sitter parse + grammar-by-extension -> structure tree
  - T14.2 synthetic delimiter cascade inside structureless spans
  - T14.3 packer (greedy, two budgets: sections + passages)
  - T14.4 edge cases (byte-chop, sub-64 merge, min-group flush)
- **T15** Identity + storage
  - T15.1 address (uri parts + rendered column)
  - T15.2 content hash (raw byte range)
  - T15.3 sp-path extraction + `sp_render`
  - T15.4 schema (contents/passages/sections) + byte-identical reassembly

## M3 — Cluster
- **T16** `embed` op
  - T16.1 in-process model runner (batch, OOM guard)
  - T16.2 `(hash, model)` store + incremental skip
- **T17** Path-blend vector (alpha concat)
- **T18** `cluster` build
  - T18.1 UMAP reduce (params, seed, warm-init hook)
  - T18.2 HDBSCAN leaf
  - T18.3 noise attachment in original combined space
  - T18.4 persist members/coords/flags
- **T19** Known-group + coverage test harness

## M4 — Brief
- **T20** `condense` op + content-hash cache
- **T21** `brief` (level-1) + provenance (model/prompt/cost)
- **T22** Upper levels to root
  - T22.1 embed + cluster briefs (reuse pipeline on brief text)
  - T22.2 `brief-upper` (pure-abstraction) op
  - T22.3 recursion-to-root controller
- **T23** Freshness
  - T23.1 mechanical faithfulness gate
  - T23.2 member-set signature + prompt-hash invalidation
- **T24** `maintain` orchestrator

## M5 — Recall
- **T25** Passage index
  - T25.1 passage vector index
  - T25.2 FTS5 over path + body
  - T25.3 brief passages into same store (`node://`)
- **T26** Legs
  - T26.1 vector leg (z-floor)
  - T26.2 keyword leg (BM25 z + vector support)
- **T27** RRF fusion + cap + empty -> explore
- **T28** `recall` endpoint + calibration test

## M6 — Export  (MVP)
- **T29** Collapse stored tree -> N agent-facing levels (branching shape)
- **T30** MD render (child listings, brief, Caution, notes)
- **T31** `GET export` endpoint (one body)
- **T32** `hrono tree export` — write folder tree to disk

## M7 — Lifecycle
- **T33** `sync` diff — new/changed/deleted/moved classification
- **T34** Incremental placement
  - T34.1 changed-chunk sticky pre-batch-centroid re-check
  - T34.2 new-chunk nearest-centroid placement + TAU
  - T34.3 moved/renamed in-place (reuse content vec)
  - T34.4 deleted + dissolve-below-2
- **T35** Incubator
  - T35.1 store + pending query
  - T35.2 drain mini-pipeline (emit density-core only)
  - T35.3 force-assign residual + `forced` flag
  - T35.4 aging (force-assign after N batches)
- **T36** `propagate`
  - T36.1 judge call (batched per topic, best-of-3)
  - T36.2 cascade climb none/minor/major
  - T36.3 drift counter + D_MAX
  - T36.4 `update_log`
- **T37** `monitor` — misfit rate (global + per-topic, incremental sampling)
- **T38** `repair` — split / migrate / dissolve
- **T39** `settle`
  - T39.1 churn counter + trigger (+ misfit backstop)
  - T39.2 warm UMAP rebuild (init = stored coords)
  - T39.3 membership diff + selective re-brief

## M8 — Breadth
- **T40** Source-reader port abstraction (interface all readers implement)
- **T41** Git discovery
  - T41.1 `bitbucket-workspace` (enumerate + validate + clone)
  - T41.2 `github-user` (enumerate + validate + clone)
- **T42** `confluence` — reader + scope selectors + validation + identity/version
- **T43** `notion` — reader + scope selectors + validation + identity/version
- **T44** Providers
  - T44.1 `openai` (chat + embed) + validation
  - T44.2 `claude-code` + CLI-login check
  - T44.3 `openai-compatible` + endpoint validation

## M9 — Manual edits
- **T45** Pins
  - T45.1 pin flag + storage
  - T45.2 `brief` regen skips pinned
  - T45.3 `settle` honors pinned membership/parenting
- **T46** Brief override + rename + notes
- **T47** Structure surgery
  - T47.1 reparent
  - T47.2 merge
  - T47.3 manual split
  - T47.4 dissolve
- **T48** Section move

## M10 — Dashboard
- **T49** App shell + auth + context/tree switcher + role-gated views
- **T50** Node graph
  - T50.1 lazy expand/collapse + fetch
  - T50.2 layout + health encoding (size/color)
  - T50.3 non-tree edges (sibling proximity, misfit-pull, propagation path)
- **T51** Node detail + members (misfit sort) + section drawer
- **T52** Triage overview + worklist deep-links
- **T53** Jobs view + SSE live
- **T54** Activity / `update_log` view
- **T55** Config tables + dry-run modals
- **T56** Manual surgery in-UI (migrate, edit, notes)

## M11 — Hardening
- **T57** Jobs polish
  - T57.1 parent aggregation
  - T57.2 cancel (cooperative cascade)
  - T57.3 SSE events endpoint
- **T58** Shared-resource dry-run (tree-keyed impact + cost)
- **T59** `rotate-key` job (old-key proof, re-encrypt, bump key_id)
