# hrono board

Status mirrors the folder each ticket file lives in. Most-actionable first.

092-108 were raised by the end-to-end manual QA run of 2026-09-03 over three
public repos (see `.e2e/RUN-LOG.md` and `.e2e/FINDINGS.md` for evidence).

| id  | title                                                  | status  | priority | size   | depends_on      |
|-----|--------------------------------------------------------|---------|----------|--------|-----------------|
| 092 | DB connection lifecycle — rollback, IMMEDIATE, retry, health | done | blocker | big | -            |
| 093 | worker supervision — guard status write, reclaim stranded    | done | blocker | medium | 092           |
| 094 | clustering must handle small N (UMAP needs 27, raises)       | done    | blocker  | medium | -               |
| 095 | wire the incubator — nothing calls drain/age                 | done    | blocker  | medium | 094             |
| 096 | export — absolute paths break CLI, parentless briefs collide | done      | high  | medium | -             |
| 114 | a leaf node born after the build is never parented           | done    | high     | medium | 062, 086, 095   |
| 113 | forced members are flagged but nothing reads the flag        | done    | high     | small  | 086, 089, 090   |
| 097 | passages pack to ~100B not 800B; byte-chop cuts mid-token    | done    | high     | medium | -               |
| 098 | data locations must hang off the db, not cwd                 | done    | high     | medium | -               |
| 099 | batch counter bumps per changed source, not per run          | done    | high     | small  | -               |
| 100 | a pure rename ejects the file from its cluster               | done    | high     | small  | -               |
| 101 | warm UMAP init can never fire (placement writes no coords)   | done    | medium   | small  | -               |
| 120 | pin nodes.signature snapshot semantics (NOT a defect)        | done    | medium   | small  | 064, 068        |
| 122 | `update` never condenses what it ingests; brief mis-cites    | done    | high     | medium | 058, 085        |
| 125 | brief passages outlive their retired node (60% orphans)      | done    | high     | small  | 071, 102        |
| 128 | convention — a new test must be mutation-checked            | done    | medium   | small  | -               |
| 129 | forced holders starve the monitor sample past SAMPLE_SIZE   | done    | low      | small  | 113             |
| 130 | no regression test measures warm-init layout stability      | done    | low      | medium | 101             |
| 131 | build_tree reads a BROKEN clusterer as "top is root"        | done    | medium   | small  | 112             |
| 133 | only propagate reports an outcome; placing ops report none  | done    | medium   | medium | 132             |
| 135 | briefs are never competitive in recall; two constants met   | done    | high   | medium | 134, 071        |
| 136 | the CLI working-directory assertion is vacuous              | done    | low      | small  | 107             |
| 140 | the keyword leg retrieves nothing; it only corroborates     | done    | medium   | medium | 134, 135        |
| 137 | `sync` — one op that brings a tree up to date, in order     | done    | high     | medium | 085,087,089,090,122 |
| 138 | `hrono tree sync` + config CLI, PUT-creates, envelope, hint | done      | high     | medium | 137             |
| 139 | `POST /jobs` — the admin-only debug door                    | done      | medium   | small  | 138             |
| 134 | sweep the corroboration trade; can a brief corroborate?     | done    | high     | medium | 127             |
| 132 | an op can decline work and still report success             | done    | high     | medium | 105, 087        |
| 126 | recall window diversity rule (UNBLOCKED: PO ruled)               | done    | high     | small  | 102             |
| 127 | a paraphrased question recalls almost nothing                | done    | high     | medium | 102             |
| 123 | upper-level attachment below TAU has no corrective (MEASURED)| done    | high     | medium | 113, 114        |
| 102 | recall — brief URI footer indexed; no per-document diversity | done    | high     | medium | 103             |
| 103 | brief output guard + faithfulness gate false positives       | done    | high     | small  | -               |
| 104 | filter — excludes replace defaults; SVG assets ingested      | done    | high     | small  | -               |
| 105 | judge verdict parsed by substring over prose replies         | done    | high     | small  | -               |
| 106 | SPLIT into 137/138/139 — operator surface             | done    | high     | big    | 092, 093        |
| 107 | `claude-code` headless CLI backend as a Completion provider   | done      | high     | medium | -               |
| 108 | convention — a seam ticket must also test the real backend   | done    | medium   | small  | -               |
| 110 | propagate re-run not idempotent — double judge cost/drift | done    | high     | small  | 087, 093        |
| 111 | /health reports the supervisor thread, not the reclaimer  | done    | medium   | small  | 093             |
| 112 | corpus below the smallest clustering rung builds nothing | done    | medium   | small  | 094             |
| 109 | job errors carry a code, not a raw driver string       | done    | low      | small  | 092, 027        |
| 141 | the sources collection takes a source TYPE                 | done    | high     | medium | 055             |
| 142 | sync dispatches by source type instead of running git      | done    | high     | medium | 141             |
| 143 | filter and split stop assuming a git working tree          | done    | medium   | medium | 142             |
| 055 | generalize ingest to source-type dispatch (SPLIT: 141-143) | done    | medium   | big    | 025, 026, 032   |
| 144 | the URI's #chunk-n fragment is documented but never emitted | done    | low      | small  | -               |
| 145 | a domain error carries its own code                        | done    | medium   | small  | 109             |
| 146 | LLMError still reports internal-error (hook-blocked)       | done    | low      | small  | 145             |
| 147 | a github-user source discovers an owner's repos            | done    | high     | medium | 141, 142, 143   |
| 148 | a bitbucket-workspace source discovers a workspace's repos | done      | medium   | small  | 147             |
| 149 | a confluence source ingests the pages of its scoped spaces | done      | high     | medium | 143             |
| 150 | a notion source ingests the pages shared with it           | done      | high     | medium | 149             |
| 151 | the openai provider — completions, embeddings, a valid key | done      | high     | medium | 107             |
| 152 | the openai-compatible provider — a declared endpoint       | done      | medium   | small  | 151             |
| 153 | validate an openai-shaped connection on write             | done      | medium   | small  | 151, 152        |
| 154 | a hand-edit pins what it touched; brief regen respects it  | done      | high     | medium | 064             |
| 155 | a pinned membership or parenting survives the re-cluster   | done      | high     | medium | 154             |
| 156 | rename, override a brief, hand it back to automation       | done      | high     | medium | 154             |
| 157 | a human note on a node or section, visible in the export   | done      | medium   | small  | 154             |
| 158 | reparent, merge and dissolve a topic by hand               | done      | medium   | medium | 155             |
| 159 | split a topic by hand, through the scoped mini-pipeline    | done      | low      | small  | 158             |
| 160 | move a section into a topic by hand, and keep it there     | done      | medium   | small  | 155             |
| 161 | a DomainError reaches the client as internal-error (#145)  | done      | medium   | small  | 145             |
| 162 | a split silently releases the membership pins it destroys  | done      | medium   | small  | 155, 159        |
| 163 | surgery on an upper-level topic; who collects an orphan    | done      | medium   | medium | 158, 114        |
| 164 | an operator cannot file a parked chunk into a topic         | done      | medium   | small  | 160, 086        |
| 165 | a hand-move that empties a topic leaves its brief in recall | done      | low      | small  | 160, 125        |
| 166 | recall answers from every tree, whichever tree you ask      | done      | high     | medium | 054, 134        |
| 115 | drain persists a pool snapshot read before the lock (M11)| done    | low      | small  | 086, 095        |
| 116 | export 500s while a build is in progress (409/503)    | done    | low      | small  | 096             |
| 117 | `_materialize` aborts on an OS error; refusal wording | done    | low      | small  | 096             |
| 119 | pin #098's two unpinned guards + reset symlink boundary | done    | medium   | small  | -               |
| 121 | shape check rejects a brief that quotes a question     | done    | medium   | small  | 103             |
| 124 | build_tree reports success while the map is unreachable | done    | medium   | small  | 114             |
| 118 | lock pattern misses package-lock.json / pnpm-lock.yaml  | done    | low      | small  | 104             |
| 042 | users.modified_at — last-modified stamp                | done    | low      | small   | 005, 033        |
| 043 | named service tier — only when logic grows             | backlog | low      | medium | -               |
| 044 | test hygiene — @pytest.mark.parametrize sweep          | done    | low      | medium | -               |
| 046 | optional OS-keychain backend for profile token         | backlog | medium   | medium | 009,036,037     |
| 048 | unify CLI error boundary                               | done    | medium   | medium | 009,011,027,033 |
| 049 | order modules top-down (helpers below)                 | done    | low      | small  | -               |
| 050 | job priorities — order queue beyond FIFO               | backlog | low      | small  | 022, 023        |
| 051 | DESIGN — first-class job dependencies (DAG)            | done    | medium   | big    | 022,023,024     |
| 052 | job progress tracking — derive parent % from leaves    | done    | low      | medium | 022,023,024     |
| 053 | DESIGN — pure domain exceptions + mapping layer        | backlog | medium   | big    | 027, 048        |
| 054 | a named tree clusters its OWN sources, not the whole corpus    | done      | high     | medium | 040, 138        |
| 056 | split the registry package (engine/collections/valid.) | done    | low      | small  | 055             |
| 076 | reserve `node-` source-name prefix (brief key collision)| done    | low     | small  | 013, 071        |
| 077 | vec0/ANN shadow index for recall (bound latency at scale)| backlog | medium  | big    | 069, 072, 075   |
| 084 | committed regression test — one-file-change partial count| done    | medium  | small  | 068, 065        |
| 067 | role->model mapping + cross-model condensation read    | done    | medium   | medium | 058, 059        |
| 091 | `settle` — warm reconcile + selective re-brief (T39)   | done   | high     | big    | 087,040,068,089 |
| 090 | `repair` — split / migrate / dissolve (T38)            | done   | high     | medium | 089, 086, 085   |
| 089 | `monitor` — misfit rate global + per-topic (T37)       | done   | high     | medium | 085, 040        |
| 088 | extend prompt guard to judge {source}/{summary}       | done   | medium   | small  | 066, 087        |
| 087 | `propagate` — judge cascade marks ancestors stale (T36) | done   | high     | big    | 085,064,059,061 |
| 085 | incremental `update` op — sticky + centroid place (T34)| done   | high     | big    | 083,068,040,086 |
| 086 | incubator — pending pool + drain + force-assign (T35)  | done   | high     | big    | 040, 068        |
| 083 | `sync` diff — new/changed/deleted/moved (T33)          | done   | high     | medium | 025, 032        |
| 068 | stable cluster node ids / incremental placement (T34)  | done   | high     | big    | 040,059,062,064 |
| 082 | export: single-root guarantee in #062 (multi-root fix) | done   | high     | medium | 062,061,078,079 |
| 081 | export: `hrono tree export -o <dir>` (T32) — MVP CLOSE | done   | high     | medium | 080, 010        |
| 080 | export: `GET export?levels=N` endpoint (T31)           | done   | high     | medium | 078, 079        |
| 079 | export: MD render (brief/children/Caution/sections) T30| done   | high     | big    | 078,032,059,061 |
| 078 | export: collapse stored tree -> N agent levels (T29)   | done   | high     | medium | 062, 059, 061   |
| 075 | `recall` endpoint + CLI + calibration (T28)            | done   | high     | big    | 074, 071, 010   |
| 074 | RRF fusion 70/30, cap 10, empty->explore (T27)         | done   | high     | medium | 072, 073        |
| 073 | recall keyword leg — BM25 z>=6.0 + support (T26.2)     | done   | high     | medium | 070, 072        |
| 072 | recall vector leg — path-blend, z>=3.5 (T26.1)         | done   | high     | medium | 069             |
| 071 | brief passages into the store, `node://` (T25.3)       | done   | high     | medium | 059,030,069,070 |
| 070 | FTS5 index over passage path + body (T25.2)            | done   | high     | medium | 032             |
| 069 | passage vector index (T25.1)                           | done   | high     | medium | 032, 035, 039   |
| 065 | `maintain` — M4 full-build easy button (T24)           | done   | high     | big    | 059,062,064,... |
| 062 | recursion-to-root controller (T22.3)                   | done   | high     | medium | 060, 061        |
| 063 | mechanical faithfulness gate on briefs (T23.1)         | done   | medium   | medium | 059             |
| 061 | `brief-upper` pure-abstraction op (T22.2)              | done   | high     | medium | 060, 057, 021   |
| 064 | member-set + prompt-hash brief invalidation (T23.2)    | done   | high     | medium | 059, 040        |
| 060 | embed + cluster briefs into next level (T22.1)         | done   | high     | medium | 059,035,039,040 |
| 066 | validate prompts keep their `{content}` placeholder    | done   | medium   | small  | 020, 021, 058   |
| 059 | `brief` (level-1) reduce op + provenance (T21)         | done   | high     | big    | 058,040,057,021 |
| 058 | `condense` op + content-hash cache (T20, map stage)    | done   | high     | big    | 057,032,023,021 |
| 057 | Anthropic text-completion client — LLM call seam (T20) | done   | high     | medium | 016, 018, 004   |
| 041 | known-group + coverage test harness for clustering (T19)| done   | high     | medium | 040             |
| 040 | `cluster` build — UMAP + HDBSCAN leaf + attach (T18)   | done   | high     | big    | 039, 023        |
| 045 | bootstrap/reset-token msg leads with `hrono profile add`| done   | low      | small  | 007,009,010,033 |
| 047 | DECISION — seed defaults (A) vs read-time fallback (B) | done    | low      | small  | 021             |

## Progress

- **M0 complete** (done/, ids 001-009): SQLite + migrations at startup, `hrono
  serve` skeleton, Typer CLI skeleton, T3 secrets-at-rest (keys table +
  fingerprint, master-key startup load + reconcile, Fernet cipher), T4 auth
  (users + token hashing, Bearer middleware + role gating + users routes,
  bootstrap admin), DB single-writer threading model, T5.2 CLI context store.
  The server is the sole authorization boundary; secrets are encrypted at rest.
- **M1 complete** (done/, ids 012-021): all four registry collections
  (sources/connections/models/prompts), git/anthropic/model validation, and
  prompt default seeding + default-reset + template-hash - all on the one
  descriptor-driven base with generic seams (no per-collection engine branch).
- **M1 detail** (done/, ids 012/013/015/016/018): #012 = T6
  descriptor-driven registry base (one engine walks a per-collection descriptor;
  role gating, secret encryption+masking via the cipher, validation-hook seam)
  instantiated as `sources` (T7.1). #013 = T7.2 git validation. #015 = T8.1
  `connections`. #016 = T8.2 anthropic validation. #018 = T9.1 `models`
  (secretless). #019 = T9.2/T9.3 model validation. Adding each collection left
  the engine unchanged; #019 made the one base change so far - a generic
  `ValidationContext(database, cipher)` threaded into every hook so a validator
  can read+decrypt a sibling collection (git/connection hooks ignore it).
- **M2 (Ingest) building out**: T11 jobs framework COMPLETE - #022 schema +
  #023 worker/op-registry/endpoints + #024 scope resolver + fan-out (parent +
  one atomic leaf per item; parent never claimed via claim_next NOT EXISTS
  children; standalone jobs still run; first M2 code on the #027 AppError layer).
  Ingest ops: #025 `sync` DONE (4937f84) - git clone/pull to
  `.hrono/cache/sources/<name>` + commit-SHA version; the source token is
  supplied via a transient env-based credential helper and NEVER persists to the
  cache/.git/config (one qa security bounce fixed a cleartext-token leak). The
  shared `git_auth` also hardened #013. #026 filter DONE (7ab6951) - glob
  exclude + size cap + null-byte sniff, defaults-as-data; one qa security bounce
  fixed a symlink-traversal vector (a link escaping the cache could ingest host
  files) by skipping symlinks + not descending symlinked dirs. **T14 split
  authored**: #029 structure
  tree (tree-sitter parse by extension + synthetic delimiter cascade
  ["\n\n","\n",". ",","," "]) -> #030 greedy two-budget packer (section 10240 B /
  passage 800 B, min_para 64, min_group 100) + edge cases (byte-chop, sub-64
  merge, min-group flush). #029 structure tree DONE (c31c155) - tree-sitter parse
  + synthetic cascade, leaves tile the file byte-for-byte (exact-cover verified
  over 134 inputs incl. adversarial); this tiling exactness is what #032's
  reassembly relies on. Settled recipe = prototype app/structuring.py (rewrite
  clean). #030 packer DONE (b22bc7f) - greedy two-budget pack (category section
  budgets + passage 800 B), byte-chop/min_group/sub-64 merge; one qa bounce
  fixed a crumb-merged byte-chop ballooning a passage past budget. **T14 split
  COMPLETE** (029+030): two-level byte-identical reassembly + <=800 B passages
  verified over real files + adversarial minified shapes. Byte-identical
  section<->passages nesting is the load-bearing invariant #032 relies on.
  #031 identity DONE (64fe378) - 4-part fragment-free URI + rendered, content
  hash = SHA-256 of the byte range (dedup/embed-once key), structure path +
  sp_render (reconstructed from the tree; packer kept pure). **T15 remaining**:
  #032 storage DONE (a534753) - contents(hash PK, dedup) / sections(4 address
  parts + URI, content_hash FK) / passages(section FK cascade, sp_paths); the
  `split` op (sync->filter->split->store, idempotent per-source txn) proves
  byte-identical reassembly FROM the DB (section == concat of its stored
  passages == file range). **M2 (Ingest) COMPLETE** (022-026, 029-032). Precise
  model: how-hrono-works.md.
- **M3 (Cluster) building out**: #035 = T16 `embed` op DONE (693836f) - in-process
  sentence-transformers runner (batched, OOM halve-and-continue, bounded LOAD),
  vectors keyed (content_hash, model) as float32 blobs (embed-once / incremental
  skip); embedding runs OUTSIDE the #008 lock. PO ratified the blob-table shape
  (vec0 can't do multi-model per-row-dims; a vec0/ANN shadow index is a
  T18/recall concern) and the lazy-optional backend (#038 adds the install
  extras). Next: #039 = T17 path-blend (combined = sqrt(1-a)*content (+)
  sqrt(a)*path, a=0.5, so dot = blended sim) -> #040 = T18 cluster build (UMAP-25
  cosine fixed-seed -> HDBSCAN min_cluster_size=5 euclidean leaf -> noise attach
  in combined space -> persist members/coords/flags; warm-init seam for T39).
  #039 path-blend DONE (16e1992) - blend identity verified to float epsilon,
  ALPHA=0.5 baked, path vectors reuse the content-addressed embed store, combine
  on the fly. #038 embed install-extras DONE (7c97921) - `hrono[embed]` opt-in,
  default install lean. #041 = T19 known-group + coverage harness (planted
  clusters + recovery threshold + coverage + determinism + perturbation teeth).
  Baked constants from clustering-lifecycle.md. After M3 -> M4 (Brief). #040
  cluster build DONE (77249c3 feat + 5389ea3 test-fix) and CLOSED by PO
  (2026-08-22): T18 bottom-level build complete - UMAP-25 cosine seed-42 ->
  HDBSCAN leaf min_cluster_size=5 -> noise attach by dot in the ORIGINAL combined
  space -> persist nodes/node_members/section_coords (migration 0009); heavy
  compute runs outside the #008 lock (load -> release -> compute -> re-acquire),
  warm-init seam wired for T39. One qa bounce (test-only teardown race: the two
  cluster worker tests omitted `worker.join()` after `stop()`, so `close()` raced
  an in-flight `claim_next` -> ~1-in-6 SIGSEGV; fixed by joining, PO re-ran the
  test 15x = 0 segfaults). PO drove the REAL pipeline: 4 planted topics recovered
  1:1, deterministic labels+coords, every section assigned, coords 25-d. PO spun
  off #054 (backlog): `tree` is a job-level name with no sections->tree mapping,
  so a build clusters ALL embedded sections into one tree - correct for the
  single corpus today, revisit when M4 named trees / M8 multi-source land.
  **M3 (Cluster) COMPLETE** (035, 038, 039, 040, 041). #041 = T19 harness DONE
  (878c1fb) and CLOSED by PO (2026-08-23): planted-K-group fixed-seed fixture ->
  real #040 build -> ARI recovery (RECOVERY_THRESHOLD=0.80, correct recipe 1.0),
  full coverage, determinism, and regression TEETH proven (no-UMAP -> 0.4275,
  wrong min_cluster_size=60 -> 0.0). In-harness ARI decoupled from sklearn
  (matches to ~1e-17). PO independently re-ran teeth + full suite (395/1 skip).
- **M4 (Brief) building out**: T20 authored, split into two on the codebase
  reality that no LLM completion client exists yet (only connection validation)
  and models carry no `role` field. #057 = Anthropic text-completion client (the
  injectable `(text, usage)` call seam every M4 op needs; cipher-fed credential;
  clean `LLMError`) -> #058 = T20 `condense` op + `condensations` content-hash
  cache (map stage: per-section condense via the seeded condense prompt, cached
  by content_hash so a re-run makes ZERO LLM calls = the incremental lever; LLM
  outside the #008 lock like #035/#040). Recipe baked from summarization-
  experiments.md (no token cap, verbatim identifiers, GOTCHA lines). Flagged
  open questions for dev: (a) JobContext does not expose the cipher yet (#057
  is the first job op needing a decrypted secret); (b) role->model has no storage
  yet — recommended YAGNI default is "resolve the sole text model" (mirror
  embed/model.py), defer a role-mapping config until multiple text models exist.
  Next reduce stage (per-cluster brief + provenance) is T21.
- **M4 (Brief) COMPLETE** (done/, 057-066): T20 condense (#058) on the #057 LLM
  client -> T21 brief reduce + provenance (#059) -> T22 upper levels to root
  (#060 cluster-briefs, #061 brief-upper, #062 recursion controller) -> T23
  freshness (#063 mechanical faithfulness gate FLAG policy, #064 member-set +
  prompt-hash invalidation) -> T24 `maintain` easy-button (#065), plus the #066
  `{content}` prompt guard. A source now ingests -> splits -> embeds -> condenses
  -> clusters -> briefs -> recurses to a single root via one `hrono tree maintain`.
  Incremental only where M4 allows: condense/embed skip unchanged (content-hash);
  the cluster/brief layers full-rebuild each run because `cluster` mints fresh
  node ids and `briefs.node_id ON DELETE CASCADE` wipes briefs — near-zero brief
  layer needs stable ids = M7 incremental placement, spun off as #068 (high, M7).
  PO decisions: role->model deferred (#067, sole-text-model default holds);
  `tree` CLI grammar settled verb-first (`tree maintain <name>`, endpoint
  canonical) — M5/M6 `tree op`/`export` follow it. One dev STOP on #065 (correct
  escalation: near-zero-second-run was an M7 promise on an M4 ticket; PO
  re-scoped + spun #068).
- **M5 (Recall) AUTHORED** (todo/, 069-075): frozen recall recipe from
  how-hrono-works.md, constants baked. T25 passage index (#069 passage vectors
  path-blended a=0.5, #070 FTS5 over path+body, #071 brief passages into the same
  store under `node://.../@<member-signature>`, origin-tagged) -> T26 legs (#072
  vector leg z>=3.5 over the query's own distribution, #073 keyword leg BM25
  z>=6.0 WITH vector support z>=3.0 — never alone) -> T27 #074 weighted RRF 70/30
  k=60 cap 10, empty->explore -> T28 #075 `POST /trees/<name>/recall` (reader,
  synchronous) + `hrono recall` CLI + the calibration test (planted-answer
  recovers, strict-miss -> explore message). After M5 -> M6 (Export = MVP).
- **M5 (Recall) COMPLETE** (done/, 069-075): passage index (069 vectors / 070
  FTS5 / 071 brief `node://` passages) -> vector leg z>=3.5 (072) + keyword leg
  z>=6.0 with vector-support z>=3.0, never alone (073) -> weighted RRF 70/30 k=60
  cap 10, empty->explore (074) -> `POST /trees/<name>/recall` (reader, sync) +
  `hrono recall` CLI + regression-grade CALIBRATION (075). The read door works:
  planted-answer recovers through vector->fusion, strict-miss fails safe to the
  exact explore message, tiny corpora never emit a low-confidence hit. Frozen
  recipe, constants baked, no knob in the API. Two forward notes captured: #076
  (reserve `node-` source prefix, low) and #077 (vec0/ANN shadow index — recall
  currently scans all passages under the DB connection, O(N) latency + writer
  contention at scale; MVP-fine, medium/M11). Every M5 ticket gated in isolation
  (worktrees) against the recurring concurrent-WIP hygiene issue.
- **M6 (Export = MVP) AUTHORED** (todo/, 078-081): T29 collapse the deep stored
  tree to <= N agent-facing levels, narrow-at-root/wide-at-leaves (078) -> T30 MD
  render — stored brief (with its Caution), MECHANICAL child listings (no
  hallucinated links), byte-identical section reassembly at leaves, notes-if-
  present; emits a path->content mapping (079) -> T31 `GET /trees/<name>/export?
  levels=N` reader endpoint (080, payload-shape open question: JSON path->content
  manifest recommended vs the spec's "one MD body") -> T32 `hrono tree export
  <name> -o <dir>` materializes the folder tree to disk with path-traversal safety
  (081). Completing 081 = **MVP**: a source becomes a walkable exported map on
  disk plus a recall endpoint. After M6 -> M7 (incremental lifecycle; #068 is its
  linchpin).
- **M6 (Export) COMPLETE (078-082) = MVP REACHED.** T29 collapse (078) -> T30 MD
  render (079) -> T31 endpoint (080) -> T32 CLI (081), plus #082 the single-root
  build guarantee (option b: `_collect_root` in #062 parents a non-reducing top
  level under one root + brief-uppers it) that closed the multi-root export-
  orphaning gap qa found. **MVP (M0-M6, T1-T32) is fully complete and airtight:**
  a git source ingests -> splits -> embeds -> condenses -> clusters -> briefs ->
  recurses to a single root, is recallable (`POST /recall` + `hrono recall`), and
  exports to a walkable folder tree on disk (`hrono tree export`). Every M6 ticket
  gated in isolation; two qa bounces caught real defects (078 levels=1 crash on
  user input; 079 sibling-heading dir collision dropping a subtree). Real-model/
  real-LLM end-to-end is the standing manual step (no creds in dev env).
- **M7 (Lifecycle) STARTED** (the incremental-update differentiator, recipes baked
  from clustering-lifecycle.md). Foundation authored first; the dependent machinery
  (T35 incubator / T36 propagate / T37 monitor / T38 repair / T39 settle) is HELD
  until the placement foundation lands, to avoid rework (same discipline as holding
  M5 during M4). In todo: #083 = T33 `sync` diff (new/changed/deleted/moved
  classification between commit-SHA versions) + #068 promoted = T34 incremental
  placement substrate (stable node ids / sticky re-check — the linchpin; note
  #068's acceptance already covers T34.1 sticky pre-batch-centroid re-check and the
  propagate-upward gap). After the foundation: author T34.2-4 (nearest-centroid +
  TAU, moved/renamed, deleted+dissolve), then T35-T39.
- **E2E hardening wave (092-112, from the 2026-09-03 three-repo run)**: the two
  server blockers closed first (#092 connection lifecycle, #093 worker
  supervision), then **#094 CLOSED 2026-09-14** — the one that unblocks the
  headline M6 deliverable. It was not a crash guard but a spec compliance fix:
  `how-hrono-works.md:109` requires the same pipeline "with dimensions and
  `min_cluster_size` scaled to the point count", and `cluster/build.py` applied
  the baked LEAF constants at every level, so an upper level of 7 briefs was
  reduced with parameters meant for thousands of sections and died in scipy.
  Now a two-rung `LADDER` in `cluster/recipe.py` (UMAP-25/mcs-5 at N>=27, the
  spec's UMAP-10/mcs-3 at N>=12, `ClusterError` below) scales every call site —
  `cluster`, `cluster-briefs`, `incubator.drain` — with no plumbing, and no
  driver exception escapes the backend. One qa bounce caught a real blocker the
  ladder created: warm `init` (stored coords, `clustering-lifecycle.md:14,97`)
  and the recipe could disagree on width once two rungs existed, permanently
  wedging `maintain` AND `settle` for any corpus shrinking across N=27; fixed by
  `_fits` dropping a stale-width init (self-healing — `replace_tree` rewrites
  coords at the new width, so the next build is warm again). PO drove the REAL
  e2e database (7 leaf topics, 104 sections, the run that died): `build_tree`
  now yields levels `[(0,7),(1,1)]`, one root with all 7 children, 8 briefs, and
  the export renders 102 files INCLUDING `root.md`. **F15/F16/F17/F18 are dead;
  M6 export is usable again.** Two follow-ups ruled on at close: #108 re-scoped
  (094's own real-backend tests delivered its teeth; what remains is the
  standing rule that a seam-introducing ticket must test the real backend once)
  and #112 promoted to todo with the product call made (a sub-12-section corpus
  COLLECTS into one leaf topic, the same move `_collect_root` makes at the top —
  it does not fail).
- **#095 CLOSED 2026-09-14 — the last blocker. No blockers remain.** F29's
  incubator was a write-only pool: `park` was the only production caller, so two
  chunks sat parked for ever, in no node, in no brief and in no export. Now the
  pool is DRIVEN — `update` ages then drains at the end of every batch's
  placement, `settle` drains after its warm reconcile and before `brief`, and a
  full `cluster` rebuild `sweep`s the rows it obsoletes — with every outcome
  written to `update_log` through the new shared `db/update_log.py` writer (
  propagate's private `_log` lifted, not copied). The pool is visible at last:
  `GET /trees/{name}/pending` (reader) and `hrono tree pending <name>`.
  Two qa bounces, both real. The first found a DATA MODEL error, not a bug: the
  pool was keyed by content hash while membership is per section, so under the
  ALPHA-0.5 path blend two identical bodies at different paths could not be
  represented by one row — one homes, its twin parks, and `sweep` then retired
  the shared row and stranded the twin in no node AND no pool, worse than F29.
  Fixed at the model by migration `0022_pending_by_section` rather than patched
  at the callers: the pool is the complement of `node_members`, so it is keyed
  the same way, and a deleted section now takes its pool row with it. The second
  found a docstring claiming more than the code did (a drained leaf is briefed,
  NOT parented) — corrected and pinned by a test that goes red when #114 lands.
  PO drove the real e2e database: migration 20 -> 22 applies clean and retires
  both stale rows, a genuinely-homeless row constructed by hand IS carried
  across, and `age` then rescues F29's `docs/unrelated-cooking-notes.md` into
  node 8 (`forced=1`, similarity 0.2805, one `update_log` row) with the #086
  invariant holding over all 94 corpus sections. `tests/cluster/invariant.py`
  makes that invariant a reusable assertion for every lifecycle test.
  Three follow-ups ruled on at close: **#114 -> todo, high** (a drain-emitted
  leaf is never parented, so it stays out of export; PO decided the rule:
  ATTACH-ONLY, mirroring #085 placement, because re-clustering level 1 for one
  new leaf inverts the incremental promise). **#113 -> todo, RAISED to high**
  (forced members are flagged and nothing reads the flag; #095 industrialised
  the producer without the corrector, so sub-TAU marriages now accumulate
  permanently in briefs — and #104's ingest filtering does NOT cover it, since
  no glob can tell that a cooking note is off-topic for a code repo).
  **#115 stays backlog/low, M11** (drain's read/compute/write window is
  unreachable under one-server/one-worker and is the settled shape's, shared
  with `cluster/op.py`; scope broadened to both call sites, promote it the day a
  second writer is proposed).
- **#096 CLOSED 2026-09-14 — `hrono tree export` actually writes the map.**
  F19: `render` emitted a leading slash on 93 of 94 keys, pathlib rerooted the
  join, the traversal guard refused the first entry and the command aborted —
  zero files. F20: `_directory` returned `""` for every parentless node, so six
  of seven briefs silently overwrote each other on one dict key, and
  `load`'s `max(node_level, ...)` served one repo's brief as `root.md` for a
  three-repo map. Now: `_under` keeps the root's own sections relative, the
  `_directory` walk terminates at the ROOT so every non-root node owns an
  id-suffixed directory (two briefs are uncollidable by construction), `_root`
  raises the new `Internal` 500 on a forest per the PO resolution, and
  `_materialize` lstrips before the guard, refuses-and-counts instead of
  aborting, and reports "Wrote N files" + "refused N of M".
  One qa bounce, and a sharp one: dev's own `lstrip` REGRESSED `"/"` from
  cleanly-refused to an unhandled `IsADirectoryError` that ate every entry after
  it — the F19 shape reintroduced one input class over. Fixed by
  `if target == base or base not in target.parents:`, graded against the three
  params that discriminate.
  PO drove it on a live server over a copy of the real corpus: the forest state
  gives a 500 with exact `details` and a one-line CLI refusal (0 files, exit 1);
  with a root added, **exit 0, 102 files, 7 `brief.md` in 7 distinct
  directories, `root.md` present, 0 files outside `--out`**, and the manifest
  has 0 absolute paths, 0 duplicate keys and **all 7 brief directories linked
  from `root.md`** — the map is walkable, not just written. Twelve hostile paths
  probed against a canary: all refused and counted, no exception, the entry
  after the bad one always lands.
  **Standing rule set at close: refuse what cannot be rendered correctly;
  degrade what can.** A forest at the top has no entry point (refuse, 500); an
  unparented leaf below the top still has one root and a complete map (degrade —
  it exports, just unlinked, which is #114). Refusing the latter would take the
  headline deliverable hostage to a lesser known defect.
  #114's harm was corrected in both `settle.py` and the ticket before anyone
  designs against it: after #096 a drained orphan leaf IS written to the export;
  what it lacks is the `root.md` link. PO re-confirmed the attach-only design —
  `root.md`'s child links are mechanical from the parent edges, so parenting is
  the ONLY thing that produces reachability. Two filings confirmed at low:
  **#116** (the forest 500 is also reachable transiently mid-build; wants
  409/503 with a running-job check, keeping the 500 for a permanent forest) and
  **#117** (`_materialize`'s write is unguarded against `OSError`; PO corrected
  its exception name to `FileExistsError` and folded in the refusal-message
  wording fix). Two qa nits took no new cards: the ragged `settle.py` docstring
  routes to #114 (which rewrites that paragraph), the message wording to #117.
- **#104 CLOSED 2026-09-14 — the corpus stops paying for junk.** F4: a source's
  own `exclude` REPLACED the baked defaults, so excluding one directory silently
  lost `node_modules` and lockfile protection. F5: SVGs sailed past the
  null-byte sniff and cost 12 of 92 sections — 13% of the corpus and 13% of the
  condense spend — then clustered into a junk topic that was one seventh of the
  map. Now `DEFAULT_IGNORE` is a data table grouped by WHY (vendored, locks,
  assets, tabular, generated) beside the extension table, and `filter.py` is
  rebuilt around a frozen `_Rules` with three layers: the caller's `exclude`
  always wins, the baked groups EXTEND it, and `include` / `include_generated` /
  `replace_defaults` re-admit. All three validated at the API boundary via
  `GitFilter`, so a typo is a 422, not a silently-ignored knob. The size, null-
  byte, zero-byte and symlink gates are not patterns and cannot be dropped —
  proven at the maximum escape hatch.
  Measured delta on the three real repos (PO re-measured read-only): the four
  SVGs are exactly F5's 12 sections, six chalk `source/vendor/**` files go, uuid
  is untouched, and hunting the other direction finds NO `.py`/`.md`/`.go`/
  `.rst`/first-party `.js` lost. Segment-matching globs keep
  `src/vendored_helpers.py`, `src/vendor.py`, `third_party_utils/x.py` and
  `roadmap.md`.
  **#099 was RE-SCOPED at this close, and this is the tick's most valuable
  finding.** qa probed 099's stated residual and found no reachable state; PO
  re-probed independently over 252 combinations (18 degenerate inputs x 14
  extensions — whitespace, comments, BOM, NBSP, zero-width space, CRLF, form
  feed) and **every non-empty input yields at least one section**. `split()`
  returns `()` only for genuinely empty bytes, which #104's zero-byte gate now
  stops first. So 099's "seen, produced no sections" marker would guard a state
  that cannot occur, and its motivating repro (`py.typed`) is fixed here. 099 is
  now only the `_next_batch`-once-per-run half — which matters MORE than when
  filed, because #095 wired ageing to force-assign every update and #113 means a
  premature force-assignment is never revisited: an over-counting batch becomes
  permanent brief pollution. Renamed, re-scoped, still high/small.
  **#118 confirmed at low** (`**/*.lock` misses `package-lock.json` and
  `pnpm-lock.yaml`; PO verified the three e2e repos hold only `uv.lock`, so the
  re-run cannot surface it) with the case-semantics documentation folded in:
  the baked list matches case-insensitively (a safety net must), the caller's
  globs literally (their instructions, like every glob tool) — **keep the
  behaviour, document it**, since unifying breaks something either way.
  **OPEN for the human PO**: chalk's six `source/vendor/**` files are real
  content, not junk — the old node-2 brief named them explicitly. Bringing them
  back is one line of source config (`"include": ["**/source/vendor/**"]`), no
  code change. Decide before the re-run.
- **#098 CLOSED 2026-09-15 — the e2e re-run's measurement hazard is gone.**
  F25 was not merely a defect but a hazard to the FINDINGS themselves: the
  September run had a server in `.e2e/run` and an op driver in `.e2e`, so one
  database grew two clone sets three commits apart, and diffing against the
  stale one invented four changes including a reversed rename. The database is
  now the anchor — `paths.py` derives `database_path` (`--db` > `$HRONO_DB` >
  default, resolved once, absolute) and `cache_root(db) = <db parent>/cache/
  sources`, threaded as an explicit ARGUMENT (serve -> lock -> create_app ->
  Worker -> JobContext -> sync/split/update), not swapped for another global.
  `JobContext.cache_root` is `Path | None` and RAISES rather than guessing.
  `grep -rn "CACHE_ROOT\|\.hrono/cache" src/` now matches NOTHING, and there is
  no `Path.cwd()` or `os.getcwd` in `src/` at all. PO measured one cache root
  from three cwds, correct resolution order, absolute result, no stray `.hrono`.
  `--db`/`$HRONO_DB` on `serve`, `reset` AND `admin reset-token`; `reset` now
  removes the `.lock` and the cache, so F32's "claims to destroy ingested
  content, leaves 10 MB of clones" is true instead of aspirational.
  **One qa bounce, the most valuable of the wave: the fix for a data-loss
  ticket introduced data loss.** With `.hrono/cache` symlinked elsewhere (an
  ordinary ops move — the cache grows), `shutil.rmtree` refuses a top-level
  symlink BY DESIGN, and the delete order meant the database and all three
  sidecars were already gone when the `OSError` escaped unhandled: exit 1, empty
  stdout, no database, intact cache — F32's exact state, freshly created.
  Fixed by refusing BEFORE deleting anything (`LinkedCache`), not by handling
  the error after; dev chose refusal over `unlink()` because the recursive
  delete is only safe while bounded inside the `.hrono` the path guard proves,
  and unlinking would leave clones on disk while claiming to destroy them.
  Any `OSError` now becomes `ResetIncomplete` carrying removed/failed, printed
  through the same helper as the success path — a half-done destructive command
  still hands over the list recovery is planned from.
  PO drove the destructive command personally on the losing layout: refusal,
  exit 1, no traceback, and **"Nothing was removed" verified literally** — all
  four files present with ORIGINAL CONTENT, link and outside payload intact;
  then the happy path removes all five and leaves the outside volume untouched.
  **Two policies settled at close.** (a) *Guard the bound, not the tree*: the
  symlink check covers the cache ROOT only. PO drove a link one level deeper —
  it is unlinked without being followed, so the outside payload survives; only
  the report is incomplete. Deepening would force `reset` to refuse any cache
  containing a symlink, and cloned repos legitimately contain them — a
  destructive command that refuses on a NORMAL install is far worse than an
  orphan in a contrived one. Settled; do not relitigate. (b) Two behaviours
  (`app.py:141`'s conditional cache_root, `reset.py:99`'s symlink arm) have NO
  test — PO confirmed by reverting both in a worktree, suite still green at 688.
  Deferral accepted as proportionate (neither is an AC, neither is
  production-reachable, both were driven) but filed as **#119** rather than left
  as a note, because "fold it into the next touch" is a hope, not a commitment.
- **#099 CLOSED 2026-09-15 — the incubator's clock is honest.** `_next_batch`
  lived in `_update_source`, so a run over three changed sources counted THREE
  batches. `tree_batch.batch` is what incubator ageing measures against
  (`current - parked_at > MAX_AGE`), so the clock ran at 3x speed on the
  re-run's own shape — a parked chunk forced after 2 runs instead of 6 — and
  #113 means a premature forcing is never revisited, so the distortion would
  have outlived the run. Now the run's number is a plain fold: `update` holds
  `batch: int | None`, each source passes it through unchanged or allocates it
  LAZILY (which is what keeps "an unchanged run never bumps" true — eager
  allocation at the top of `update` is the tempting wrong fix that still reads
  like "one per run"), and allocation sits inside the diff/reconcile
  transaction so a failed sync rolls it back. The contract is stated at BOTH
  ends, `tree/update.py` where it is written and `cluster/incubator.py` where it
  is READ — a clock only means something if the reader agrees what a tick is.
  No marker mechanism was built, per the re-scope.
  PO drove all eight subsets of THREE changing sources through the real op:
  exactly one bump whenever anything changed, zero when nothing did, regardless
  of how many sources changed — and the identical probe at `de5ef38` advanced
  once per changed source (`111` -> +3). Ageing boundary at three sources:
  survives at age 5 (`== MAX_AGE`), forced at 6, pool invariant green every run,
  parked row keeping its ORIGINAL batch throughout.

- **E2E RE-RUN BASELINE (agreed 2026-09-15, PO + qa).** The wave 092-099 is
  closed and the re-run is GO **for structural findings**: every September
  measurement hazard is gone (#092/#093 server survival, #094 clustering at
  small N, #095 incubator wiring, #096 export paths/collisions, #098 cwd cache
  divergence, #099 the batch clock). It is **NOT** a verdict on brief or recall
  QUALITY — the defects that determine quality are the ones still open, so
  quality numbers from this run are a BASELINE to compare against after
  #097/#102/#103/#105 land, not findings.
  **Pre-recorded as EXPECTED — do not re-file these as discoveries:**
  #114 (drain-emitted leaf is written to the export but unreachable from
  `root.md` — expect orphan directories), #113 (the `forced` flag has no reader,
  so a low-similarity forced chunk pollutes its brief permanently), #100 (a pure
  rename still ejects a file from its cluster), #097 (~100 B passages, not
  800 B), #102 + #103 + #105 (brief and recall quality, judge parsing), #118 (a
  `package-lock.json` is still ingested), #116 (an export issued mid-build
  answers 500 with an accurate message), #106 (no `POST /trees/{name}/update` —
  a clean 404, so the run stays script-driven), #101 (placement writes no
  coords, so `settle` reconciles COLD — expect more label churn than "warm start
  ~0 delta" promises), #110 (a second `propagate` doubles judge cost and drift),
  #111 (`/health` reports the supervisor, not the reclaimer — it can read
  "alive" misleadingly), #054 (no sections->tree mapping, so all three repos
  cluster into ONE tree — as in September), and #102's `root.md` symptom
  specifically: the child list appears TWICE, once as raw `- node N` ids from
  `brief_upper.py:101`.
  **Retry caveat**: a retried `update` job is a fresh run and allocates another
  batch — defensible and bounded (one tick per retry vs `MAX_AGE` 5), but #093
  made reclaim normal, so if the counter ends higher than the number of
  successful runs, check `jobs` for retries before filing. Five or more in a
  run, or a chunk forced early because of them, IS the trigger to file.
  **Signature prediction — WITHDRAWN 2026-09-15.** An earlier version of this
  line predicted up to two unexpected brief regenerations from "signature
  drift". That was wrong: #064 freshness never reads `nodes.signature` (its only
  reader is `store._reconcile`), so a stored signature cannot cause a re-brief.
  A membership change re-briefs because the MEMBERSHIP changed. See #120.
  **Configuration constraint**: #067 is deferred on "resolve the sole text
  model", so register exactly ONE text model or condense/brief resolution
  breaks. Run every process with the same `--db` (#098).
  **One decision still open and owned by the human PO**: the chalk
  `source/vendor/**` question from #104. Left as-is, the run's chalk topic will
  NOT hold the two vendored dependencies September's node-2 brief described, so
  a brief comparison will look like a quality regression when it is a deliberate
  scope change. Decide before the run — one line of source config either way.
- **#097 CLOSED 2026-09-15 — passages are quotable units again, and a wrong
  line of SPEC was the root cause.** `MIN_GROUP = 100` flushed a passage group
  as soon as it reached 100 bytes, capping passages at an eighth of their
  800 B budget: the real corpus packed to a **152 B median with 68% under
  200 B**, so a recall hit was a truncated sentence and the passage table was
  several times larger than intended. The fix was DELETION, not another rule —
  a group is now flushed by the budget and nothing else — plus a `_chop` that
  cuts evenly (not budget-then-remainder, which manufactured the crumbs the
  next pass had to clean up) and backs off to a whitespace edge within 10% of
  target, and a passage-level cap on `_merge_tiny` so a crumb cannot push its
  neighbour over budget into a byte-chop.
  PO re-measured both commits over `.e2e/run2/repos`: passages 1113 -> **474**,
  median 156 -> **592**, under-200 B 64% -> **15%**, over-budget 0 both sides,
  and **sections unchanged at 112** — section packing genuinely untouched, so
  clustering and briefs see the same corpus. Byte identity re-verified on all
  112 sections with 0 gaps and 0 overlaps: the load-bearing invariant survived a
  rewrite of the packer's flush rule. **Zero raw chop parts exist anywhere in
  the corpus**, so F8's mid-token cut cannot occur rather than merely not
  occurring; PO measured the counterfactual — removing the crumb cap produces 14
  shredded structural passages while saving only 6 crumbs, and an intact-but-
  short passage keeps its node and structure path where a fragment keeps
  neither.
  **ROOT CAUSE WAS THE SPEC, and PO corrected it** (`how-hrono-works.md:41`,
  dated note, old wording quoted, "do not reinstate a group-size flush"). The
  settled prototype `app/structure-split.ipynb:pack_node` flushes ONLY on
  `nxt_start - group_start > budget` — there is no 100-byte rule and never was;
  its sole small-span rule is `merge_tiny`'s 64 B `MIN_PARA`, which production
  keeps. #030 implemented the prose literally. Lesson worth carrying: when the
  spec's prose and its own settled prototype disagree, the prototype is the
  recipe — and the prose gets fixed, or the next ticket rebuilds the bug.
- **Queue after #097 (PO, 2026-09-15).** #102 now DEPENDS ON #103 and carries a
  CALIBRATION PRECONDITION: `.e2e/run2/.hrono/hrono.db` is entirely pre-097
  (786 passages, 152 B median, 68% under 200 B — measured), so a score floor
  fitted to it is fitted to a packing that no longer exists. **Re-run a full
  `maintain` before calibrating**, and never calibrate on an update-only corpus
  (bimodal: `update` re-splits only changed files). #103 is the last open ticket
  that changes what a fresh maintain PRODUCES (brief content, which recall
  indexes as `node://` passages), and a maintain costs ~16 min plus real LLM
  spend — so the order that pays for it once is **#103 -> full maintain ->
  #102**. Everything else in the high band (#100, #113, #114, #101) changes
  INCREMENTAL behaviour only and can land around that, verified against the same
  rebuilt tree. Next up by the dispatch rule is #100 (high, lowest id, small,
  incremental-only) — no conflict.
- **#100 CLOSED 2026-09-15 — a rename is no longer churn.** F27: `moved` took
  the sticky re-check, and with ALPHA 0.5 the path is half the blended vector's
  norm, so a rename ALONE could drop a working member under TAU and park it.
  Now `_in_place` re-attaches to `prior_node_id` on the predecessor's exact
  terms (similarity and forced flag), with `reconcile` carrying
  `prior_similarity`/`prior_forced`/`prior_batch` because `_drop_path` destroys
  the membership before placement runs. Two cases dev added beyond the Decision,
  both good judgement: an extension-CHANGING move is downgraded to `changed`
  (different grammar and budget, so sections pair by ordinal — this makes "a
  moved delta always has byte-identical content" true BY CONSTRUCTION), and a
  parked file's rename keeps its ORIGINAL park batch, closing an evasion nobody
  asked about (the pool is keyed by section_id since 0022, so a naive re-park
  would reset the age clock and let a periodically-renamed file dodge MAX_AGE
  for ever).
  **#120 came out of this tick and PO cut its scope in half.** qa chased an
  anomaly — the fix rewrote node 4's signature on the real database — and found
  3 of 7 stored signatures already disagreeing with their members. PO verified
  both halves:
  - **Leaf half REAL, mechanism demonstrated**: nodes 3 and 4 are drifted, and
    deleting one member section from node 1 flipped its agreement True -> False
    in a single statement. FK cascades go around all three refresh sites
    (`add_leaf_node`, `add_member`, `remove_member`).
  - **Upper half NOT a defect** — a category error in the diagnostic. Node 7
    stores exactly the child-id signature `replace_level` writes, NOT the
    empty-set hash; the apparent disagreement came from applying the LEAF
    function `node_content_signature` to a node that legitimately has no
    members. And every caller of the three refreshers targets a provably level-0
    node (`add_leaf_node` hardcodes level 0; the rest take their node from
    `membership()` or `node_centroids`, both filtered `level = 0`), so **no
    production path can reach it**. Removed from scope before anyone builds it.
  - **The finding that set the priority**: a full rebuild does not HEAL the
    drift, it CONSUMES it. `replace_tree` hands `_reconcile` the new label
    signatures and matches against STORED ones, so a drifted node advertises a
    member set that no longer exists — usually failing to match (new id, brief
    regenerated) and occasionally matching the wrong label (wrong brief). #120
    must therefore say what happens to already-drifted databases: one-time
    reconciliation, or rebuild from scratch.
  #120 was promoted to **high** on the argument that it breaks #064's freshness
  invariant in both directions. **That argument was WRONG and PO has withdrawn
  it (2026-09-15)** — see the #120 correction below. The observation (stored !=
  recomputed on nodes 3 and 4) was right; calling it drift was not.
- **FULL MAINTAIN RUN 2026-09-15 at fd15c60 — the corpus is now current.**
  2m39s. Condensations 74 -> 77: only the three genuinely missing ones were
  computed, the other 74 came from the #058 cache — which independently confirms
  PO's finding that #097 left section content hashes untouched (a re-packing
  would have orphaned the cache wholesale). Passages 905 -> 438, median 153B ->
  475B (#097 landed). Node ids [1,2,4,7,8,9,10] — exactly what PO's A/B
  predicted, including node 4 keeping its id on its snapshot. Briefs 7, **0
  flagged** by #103's guard. **#102 can now be calibrated on this corpus** (its
  precondition is satisfied); #122's evidence is preserved separately at
  `.e2e/evidence/run2-before-122-fix.db`, since this maintain masked the defect
  by condensing the three missing sections.
- **Queue (PO, 2026-09-15, SUPERSEDES the #120 gate).** **#103 -> full maintain
  -> #102.** #103 is done, so the maintain is unblocked NOW. #120 is NOT a gate
  and never should have been one: PO set that gate on a false premise and has
  withdrawn it. Measured on copies of run2, the maintain keeps **4 of 7** briefs
  as-is and only **3 of 7** with #120's prescribed fix applied — gating on it
  would have made the outcome worse. The id churn a rebuild shows (3 of 6 leaves
  retired) is inherent to re-clustering a corpus six incremental updates have
  moved on, not a signature defect.
  #101, #113, #114, #120, #122 change INCREMENTAL behaviour or documentation
  only and can land around the maintain in any order.
- **#103 CLOSED 2026-09-15 — the map's first topic can no longer be the model
  talking back.** F21: node 1's stored brief was "...not a request for me to act
  on something. Are you sharing this as a reference..." and the faithfulness
  gate passed it, because a non-answer invents nothing. New `summarize/shape.py`
  rejects exactly three shapes (empty under 40 chars, asks-the-caller,
  addresses-the-caller in the FIRST sentence only), retries once, then stores
  the second reply WITH its reason in `briefs.flagged` (migration 0023) — a
  flagged brief an operator can see beats a topic missing from the map.
  The RESTRAINT is the quality here: it deliberately does not reject a generic
  "## Summary" heading, bullets-only, unusual length, or a question ABOUT the
  material, because a false positive costs a paid retry and then pollutes the
  triage queue the flag exists to serve. The summary-2 export leak was fixed in
  the RENDERER for the same reason — summary-2 is a good brief, so demanding a
  title would retry then flag it, paying the forbidden false positive twice.
  PO ran the shape check over all 14 real stored briefs: run1 rejects 1 of 7
  (F21 itself), run2 rejects 0 of 7. **Zero false positives on real data.**
  Migration 0023 verified on a copy (22 -> 23, column present, 7 briefs
  preserved).
- **#122 FILED at high — a causal claim corrected by measurement.** qa found
  sections with no `condensations` row and attributed it to #097's re-packing.
  PO disproved that directly: running the real splitter over `.e2e/run2/repos`
  under `733549c` and `9e01051` gives **112 sections both sides, identical key
  sets, ZERO content hashes changed** — #097 moved PASSAGE boundaries only. The
  real cause: **`condense` has exactly one caller, `maintain`.** `update` never
  condenses what it ingests and neither does `settle`, so the three uncondensed
  sections in run2 are precisely the files the incremental scenarios touched
  (`rotation.py`, `signer.py`, `cooking-notes.md`), matching September's count.
  PO also found the half that sets the priority: `member_condensations` INNER
  JOINs `condensations` so an unsummarised member is silently dropped from the
  reduce input, while `member_uris` is a SEPARATE query with no such join — so
  **the brief still cites a section the model never read.** An incomplete map is
  a gap; a mis-cited one is an error, and the citation is exactly what we tell
  agents is mechanical and trustworthy. NOT #106 (that is op CHAINING; this is a
  stage missing inside `update` and would survive perfect chaining).
  **A full maintain MASKS this** — it condenses everything — so #122 carries a
  verification warning, and **run2's database must be copied before the planned
  maintain overwrites the only live evidence.**
- **#120 CORRECTION (PO, 2026-09-15) — dev stopped, and was right to.** Dev
  declined to implement #120 and escalated it as a design call. PO verified and
  **withdrew the ticket's premise**: `nodes.signature` has exactly ONE reader in
  all of `src/` (`cluster/store.py:168`, inside `_reconcile`), and #064 freshness
  never touches it — `stale_or_missing` compares the stored
  `briefs.member_signature` column against `briefs.member_signature(conn, node)`
  computed ON DEMAND, already leaf/upper aware. So the sole consumer is #068 id
  matching, **and id matching wants the snapshot**.
  The snapshot IS the mechanism: `split` deletes a source's sections and
  re-inserts identical content under new ids, so members have already cascaded
  away by the time `replace_tree` runs — the rebuild recognises a node by the
  signature it KEPT THROUGH that teardown.
  `tests/cluster/test_stable_ids.py::_resplit` is precisely that cascade delete,
  and a refresh-on-cascade sets the signature to the empty-set hash, which is
  why dev's implementation broke all three stable-id tests.
  **PO re-ran the A/B on copies of run2**: as-is keeps [1,2,4] and **4 of 7
  briefs**; with #120's fix applied it keeps [1,2] and **3 of 7**. Node 4
  decides it — its snapshot matched a rebuilt label, keeping its id and brief;
  "correcting" it made it match nothing. The prescribed fix is actively worse on
  the real database.
  **The PO error, recorded so it is not repeated**: `node_content_signature` is
  NOT the inverse of the stored value. The stored value is the member set as of
  the last WRITE; recomputing it mid-teardown legitimately disagrees, and nothing
  consumes the recomputation. Measuring `stored != recomputed` and calling it
  drift was the mistake. #120 is re-scoped to `medium` and now exists only to
  PIN that semantics — a docstring plus a test asserting a cascade delete does
  NOT refresh — so the same misreading cannot be made silently again.
- **#114 ruling (PO, 2026-09-15, after a qa rejection).** AC1 said "from
  `update` and from `settle`"; **amended to settle+maintain**, because
  attachment scores the leaf's BRIEF vector against brief-space centroids and
  `update` makes no LLM calls by design — an update-born leaf has no vector in
  that space, and its sections' content+path vectors are a different space
  entirely. PO's original Decision was under-specified, not dev's shortcut. The
  residual is bounded and self-healing (in a node, exported, unlinked only until
  the next brief pass, which its own churn tends to trigger — before #114 it was
  parked and invisible), and AC1 now REQUIRES a test proving the self-heal. The
  update-path question is recorded against **#122**, which owns whether `update`
  should condense/brief at all.
  qa's second finding is the **#113 shape one level up** and PO verified all
  three legs: `node_children.attached`/`assignment_similarity` have ZERO
  `SELECT`s in `src/`; `monitor.py` has no mention of `level`; and nothing
  re-clusters an upper level (`cluster_briefs` has one caller and `build_tree`
  breaks at the root). So `levels.py:104-108`'s claim that drift counters and
  the next reconcile correct a poor upper placement is false in all three parts.
  **Ruling: state the bound — correct the docstring in #114 — rather than build
  a reader there**, and file the corrective as **#123 depending on #113**.
  **Explicitly NOT merged with #113**: same shape, different job. #113 is
  level-0 and its consumers already exist (`monitor._misfits`,
  `repair.migrate`) so it needs a read, not a mechanism; the upper case needs
  monitor to learn about levels and repair to migrate upward. Merging would turn
  a ready small ticket into a big design one and delay the measured level-0 fix.
- **#114 CLOSED 2026-09-15 — the real map is reachable end to end.** Verified
  on the live corpus, not a fixture: `.e2e/run2` had root 7 holding only
  (7,1),(7,2),(7,4) after the maintain — the rebuild retired leaves 3,5,6,
  minted 8,9,10 and never attached them, so 6 topic directories rendered with
  only 3 linked from `root.md`. PO reproduced the repair on a copy:
  `7->8 sim 0.615`, `7->9 sim 0.594`, `7->10 sim 0.335`, **0 unparented, 6 of 6
  linked, in ONE LLM call.** Polarity now matches the schema (attached=1 = by
  proximity), similarity is recorded on every `node_children` row with 0012
  documenting the deliberate divergence from `node_members`, and the false
  "settle's drift counters correct it" docstring is replaced by an honest bound.
  Folding in the childless-root fallback was right — same defect statement,
  found by this ticket's own invariant, and shipping without it would have left
  the headline claim false on the only real database we have.
  **#123 raised to `high` and promoted**: the three live attachments are
  0.615 / 0.594 / **0.335**, every one BELOW TAU 0.70, so half the real map is
  held by low-confidence attachments nothing can review. PO also corrected an
  earlier assumption — the harm is NOT softer than #113's: a parent re-briefs
  when its child set changes, so a badly-attached child pollutes the parent's
  brief content exactly as a forced member pollutes a leaf's.
  **#122 is the root of a CHAIN**, established by qa through control (plant the
  14 missing condensations, re-run the same settle -> everything briefs and
  parents): update ingests -> nothing condenses -> no brief -> no brief vector
  -> no attachment -> unreachable. So #114's residual window is "until the next
  FULL PASS", not "until the next settle"; corrected on both tickets.
  **#124 re-scoped**: the multi-parent branch is the lesser half; the half that
  matters is that `build_tree` REPORTS SUCCESS while the map is unreachable —
  the silent-failure shape behind F16, F20 and F29. Fix the report, not the
  branch: that makes every route visible, including ones nobody has thought of.
- **#102 rulings (PO, 2026-09-17, after a qa rejection; decision-only tick).**
  **Finding 1 — BACKFILL, AC1 not amended.** PO verified 0024's justification
  ("parsing prose back into a list is guesswork") is factually FALSE: all 7 live
  briefs carry a machine-written footer with a fixed sentinel and a fixed
  per-line format, **7 of 7 exactly reconstructible**. The backfill is a
  `partition()` on a constant, no LLM call. AC1 is the ticket's headline and it
  fails on the corpus PO named for calibration (30% of the uuid window is F30
  verbatim; 47% of node:// passages are reference lists), and "a regeneration
  will clear it" means NEVER on a stable corpus.
  **Finding 2 — keyword corroboration, NOT a floor change.** The leak and the
  on-topic restoration are the same effect, so moving Z_FLOOR trades along the
  wrong axis and claws back the gain. The keyword leg is the ORTHOGONAL
  discriminator (uuid hits carry `uuid`/`v7`; "labrador puppy" hits carry none
  of its terms), and the rule is already the settled architecture applied
  symmetrically: #073 says a keyword hit is never enough alone without vector
  support, so **a vector hit the keyword leg does not corroborate must clear a
  higher bar**. Cost accepted deliberately: a genuinely on-topic question in
  vocabulary the corpus does not share gets cut — "better to cut than to leak",
  and recall fails safe to explore.
  **The pinning test is specified in five parts**, because two probes cannot
  characterise a distribution — both of dev's passed while the leak was live.
  The load-bearing part is that the absent-set and the present-set must live in
  ONE suite: without the present-set, the cheapest way to pass the absent-set is
  to raise the floor until everything is cut, which is the original defect
  restored. Each half must be able to fail the other's fix.
- **#102 CLOSED 2026-09-17 — the read door works, and AC2 is MOVED not met.**
  Four rounds. Both PO rulings held: the backfill recovered **75 member entries
  across 7/7 briefs, 0 footers left**, and corroboration landed at
  UNCORROBORATED_FLOOR 4.5 (Z_FLOOR 3.5 when corroborated) with the working
  shown and all ELEVEN absent questions exploring. The five-property suite is in
  and **the counterweight bites** — raising both floors to 12 fails eight tests,
  which was the property PO cared about most.
  dev corrected PO's mechanism from the data: "appears in the FTS match set"
  does not discriminate, because the absent question's one match scored keyword
  z **-0.37** — a stopword match. Keying on keyword z >= 0 plus dropping 54
  baked function words is the right operationalisation and independently a
  keyword-leg quality fix.
  PO drove the export on copies in BOTH states (stored, and edges-cascaded into
  #114's childless root): identical — no `## References` on root, **0 raw
  `- node N` lines**, 6/6 leaves carrying references, 69 `git://` refs. That
  identity is the point of the level guard; child count diverges in exactly the
  cascaded state, which is why the two rejections were both right.
  **A second source of URI lists was found en route**: 51 of 85 `node://`
  passages (60%) were summaries of RETIRED nodes — recall answering from topics
  that no longer exist. Filed as **#125**, confirmed structural by PO (no FK
  from the passage store back to `nodes`; `source = "node-<id>"` is a string)
  and promoted to todo/high, because a single rebuild retires half the leaves so
  orphans accumulate on every rebuild.
  **AC2 (diversity) moved to #126, explicitly NOT met.** The distinction from
  AC1: AC1 was unfinished work, AC2 is unimplemented BY DESIGN pending a product
  decision that is neither PO's nor dev's. Final evidence is worse than before —
  **10 of 10 hits from ONE document** for two of the four probes; removing the
  URI lists CONCENTRATED the window rather than diversifying it.
  **#127 filed** for the paraphrase weakness PO deferred at #103 pending the
  backfill: the backfill landed and did not help, so that question is answered.
  Its first acceptance criterion points at PO's OWN #102 ruling — a paraphrase
  has weak keyword support by construction, so it lands in the band the
  uncorroborated floor raised; if that is a material part of the loss, the trade
  is PO's to re-examine, not dev's to absorb by tuning.
- **STANDING RULE set 2026-09-17**: a justification that defers work to a future
  event must NAME the event and SHOW it actually happens. Three tickets in a row
  shipped one that does not occur — `levels.py`'s "settle's drift counters
  correct it" (#114), PO's own #120 reasoning, and 0024's "a regeneration will
  clear it". If the event cannot be shown, the work is not deferred, it is
  skipped, and the comment claiming otherwise is worse than no comment because
  it stops the next reader noticing.
- **Lesson carried from this tick**: when a defect and a recent change coincide,
  check whether the change could have caused it before attributing — one hash
  comparison across the commit boundary settled a question that would otherwise
  have sent the fix to the wrong module and left the real gap open.
- Deferred-work notes to honor when the milestone arrives:
  - The in-process embedding model-LOAD bound (the #019 note) is now called out
    in #035's acceptance criteria - honor it there when sentence-transformers
    lands.
  - For T58 (edit->invalidation): #021's `content_hash` is SHA-256 of the full
    stored config body - stable for the secretless collections that drive
    invalidation (prompts/models) but noisy for secret-bearing rows under Fernet
    nondeterminism. Fine today (unused until T58); revisit when wiring it.

## Notes

- Every new registry collection is a descriptor + pydantic model, no engine
  change. A base change to admit a collection must stay generic, never
  collection-specific.
- T6's staleness/dry-run half is DEFERRED to T58 (M11) per the spec - it needs
  trees (M2+). Do not build it into the M1 registries.
- Hardening follow-ups spun off from reviews ALL DONE: #011 (malformed config,
  434cd84), #014 (RFC-7235 case-insensitive Bearer, e7acee9), #017 (scrub master
  key from git subprocess env, 9e16d3d).
- **Error handling COMPLETE** (stakeholder request): #027 foundation (003e7f5) +
  #028 migration (8ad3388). Every error routes through `AppError` -> one handler
  -> `{"error":{code,message,details}}` envelope (grep-clean: no HTTPException/
  _KEY_ERRORS/detail= in src). Behavior preserved: opaque 401 + WWW-Authenticate
  (via `AppError.headers`), master-key fail-closed + no mutation, 500 never
  leaks. `ValidationFailed` subclasses `BadRequest`; CLI uses `cli_message()`;
  #010 client reads `error.message`. New code raises `AppError` subclasses.
- **Admin recovery** (#033 targeted + #034 nuclear): stakeholder request -
  losing the one-time bootstrap admin token locks you out of the API. Both are
  local CLI recovery commands operating on the DB file directly (no Bearer/no
  master key; trust boundary = filesystem access, granting nothing beyond what
  sqlite surgery already could). #033 DONE (895bcfb) - `hrono admin reset-token
  <user>` reissues a token with no key/token, rotates the old one out, touches
  only the target row, new token never in the DB plaintext. #034 DONE (b3c1964) -
  `hrono reset` full wipe behind explicit confirmation (never silent),
  refuse-non-hrono-path guard (can't rm an arbitrary file), only known files
  removed, serve re-bootstraps. **Admin-recovery request COMPLETE.**
- T5 CLI-client foundation complete: #009 context store + #010 HTTP client
  wrapper (commit 9ef8ca6). #036 DONE (f7be76e) - renamed client "context" ->
  "profile" across CLI/code/config/tests (atomic, behavior-preserving):
  `[profiles]` table, `hrono profile ...`, from_profile/NoProfile; unrelated
  context (ValidationContext/JobContext/LLM/tree) untouched; PO reconciled the
  external spec (implementation-notes.md -> "Profiles (kubectl/gh call this a
  context)"). #037 (low, now unblocked) fixes the Windows config location
  (%APPDATA% via platformdirs; Unix keeps ~/.hrono; HRONO_HOME wins) - client
  config path only, not the server DB.
- Baked operating constants (TAU 0.70, MAX_CAP 30, D_MAX 5, etc.) are NOT config
  - see clustering-lifecycle.md when tree work starts.
- **Process hygiene (recurring — now 5x+, ESCALATED)**: a ticket must be
  committed with the working tree left CLEAN before it moves to verifying; do not
  start the next ticket's WIP until the current one is committed. Uncommitted
  next-ticket WIP has polluted: #028 vs #026; #033 vs #029; #030-fix vs #017;
  #066 WIP vs #059; and #064 WIP vs #060 (this one gave a FALSE 8-failed pytest
  signal because #064's uncommitted edit changed `briefs.upsert`'s signature).
  Reviews gate the ticket's own commit in isolation; dev please commit AND route
  each ticket, leaving the tree clean before the next ticket's WIP.
  DECISION PENDING (stakeholder, asked 2026-08-24, away): board reinforcement has
  failed 5x, so PO raised a structural fix. PO RECOMMENDATION = worktree-per-
  ticket (each dev ticket in its own git worktree; parallel WIP cannot cross-
  contaminate one tree). Alternatives offered: a commit-clean gate before routing
  to verifying, or serialize dev to WIP=1. Until the stakeholder decides, PO
  continues to isolate-gate every review (stash foreign WIP -> gate the ticket's
  commit -> restore); reviews remain trustworthy but at extra cost per tick.
  ESCALATED FURTHER (2026-08-24, #064): the shared tree is now causing WORK LOSS,
  not just false gates — dev reported a concurrent `git reset` wiped their first
  uncommitted #064 attempt (they rebuilt and committed). A shared tree with
  multiple actors + `git reset --hard` destroys uncommitted WIP. This strengthens
  worktree-per-ticket: separate worktrees make both the false-gate AND the
  reset-work-loss failure modes structurally impossible. Do NOT run `git reset
  --hard` on the shared tree while any dev has uncommitted WIP.
- Backlog source of truth: `/Users/orest/repos/rad/hrono/build-order.md`.

## PO backlog triage, 2026-09-21

Reviewed all 31 backlog items after #106's split closed and every work folder
emptied. Promoted six to `todo`, all `medium`, and left 25.

**Promoted, and why these six:**
- **131** — `build_tree` reads a BROKEN clusterer as "the top is the root". The
  same defect #112 closed one level down, with a worse blast radius (a truncated
  tree reported as success), and #112 created the type that expresses the fix.
- **124** — its sibling: `build_tree` reporting success over an unreachable map.
  Now also carries #123's single-child blind spot, so the degenerate-upper-node
  rule gets decided once.
- **133** — the ops that force placements report nothing. Promoted BECAUSE #138
  just shipped `hrono jobs get`: an op with no result is now a visible gap.
- **121** — a brief rejected for quoting a question is a false positive in the
  guard that protects brief quality; a rejected brief is a topic with no
  summary.
- **119** — #098's data-location invariant is one of the few that has actually
  bitten us (F25). Two of its guards are unpinned.
- **084** — "one changed file re-briefs only its own topic" is the incremental
  promise as a test, and #137's chain is what it needed to be drivable.

**Left in backlog, deliberately.** The 16 `low` items are real but none
degrades the product today: test hygiene (#044, #049), YAGNI-gated job features
(#050, #052, #109), narrow edge cases (#115, #116, #117, #118), and the four
follow-ups this month's work filed on itself (#129, #130, #136, #076). The nine
remaining `medium` ones are either DESIGN tickets that want a milestone rather
than a slot (#051, #053, #055, #077), or scoped for later milestones (#046,
#048, #054, #067, #135).

**#135 is the one I will promote next** — briefs never competing in recall is
the most interesting open question on the board, and it asks whether a layer we
build and pay for on every rebuild is earning its place. It wants a session of
its own rather than being squeezed behind six small tickets.

## PO backlog triage, 2026-09-25

M9 closed and every work folder emptied, so I triaged the 14 remaining backlog
items. Promoted three; left eleven.

**#054 promoted and RAISED TO HIGH, and it is the find of this triage.** It was
parked in Aug with an explicit pull-in trigger — "when the FIRST second
tree/corpus becomes real" — and I checked the trigger rather than trusting the
park. It had already fired, through a door nobody was watching: #138 made the
tree a REQUIRED ARGUMENT of `hrono tree maintain <name>` and `sync <name>`,
while `store.section_combined_vectors` still loads every embedded section and
takes no tree at all. Driven on a six-section corpus: `maintain alpha` then
`maintain beta` yields two trees of 2 nodes and 6 members each, with all six
sections held by both. A documented command takes a name, echoes it back, and
ignores it.

This also recasts the month's cross-tree work. #158's F2 and #164's pool-scope
test both guarded a section living in two trees — a state I described at the
time as exotic, and which is in fact what the documented CLI produces on its
second run. Its design is now settled in the ticket (a tree is a set of
SOURCES, declared as registry config) because "decide with the M4 tree model"
outlived M4.

**#163 promoted, medium.** #158 refused upper-level surgery rather than guess
the rule; this is the rule, and it carries the defect underneath it — nothing
collects an orphan above level 0, because `attach_orphans` hardcodes it in both
call sites. That bound is FOREVER, which is the word its own docstring uses for
the harm it was written to fix one level down.

**#161 promoted, medium.** Small, and it is the read door: an operator whose
server has no embedding model is told "internal error" while the log says
"no embedding model available". A one-line fix for a class of failure with a
one-line remedy the user can't see.

**Left, deliberately.** #165 (low) self-heals within one `sync` and I would
rather it waited than crowded the lane. #046, #056, #050, #052, #042, #044,
#049, #043 are hygiene or YAGNI-gated and none degrades the product today.
#051 (job DAG) and #077 (ANN shadow index) are DESIGN tickets that want a
milestone rather than a slot — #077 in particular is the recall-latency
question and deserves measurement before code.

| 167 | a registry delete needs a hook; `rm` a tree arms a full recluster | done | medium | small | 054, 012 |
| 168 | `hrono recall` times out at 10s and calls it unreachable      | done      | high     | medium | 010, 074        |
| 169 | a recall before the encoder is ready should say so, not queue | done      | low      | small  | 168             |
| 170 | convention — a seam's real-backend test must run at real SIZE | done      | medium   | small  | 108, 168        |

## PO backlog triage, 2026-09-26

Promoted four, left ten.

**#170 and #167 (medium, small).** #170 writes down the convention this month
earned twice — #166 and #168 were the same shape, a real backend exercised but
not at a size where its cost or its statistics are real. A convention learned
and not written is learned again. #167 closes the footgun #054 left: deleting a
tree's config row silently arms a corpus-wide recluster, and the registry
engine has no hook to say so.

**#169 and #165 (low, small).** Both are small, both are honest gaps in
behavior this month's work created or exposed, and with the lane empty there is
no reason to make them wait for a milestone they do not need.

**Left, and why.** #051 (job DAG) and #077 (ANN shadow index) are DESIGN
tickets that want a milestone and, for #077, a MEASUREMENT before any code —
#168 just showed what a real-size number is worth. #046 is security polish with
no current pain. The six remaining low items are hygiene (#042, #044, #049,
#056) or YAGNI-gated job features (#050, #052); none degrades the product.
| 171 | the engineering conventions live in a gitignored file         | done      | medium   | small  | 170             |
| 172 | a parent job reports nothing about its children (T57.1)      | done      | medium   | medium | 133, 139        |
| 173 | cancel a job, and have its children stop too (T57.2)         | done      | medium   | medium | 172             |
| 174 | watch a job's progress live, over SSE (T57.3)                | done      | medium   | medium | 172             |

## PO — M11 opens, 2026-09-26

M9 closed and the promoted backlog is drained, so M11 is authored: #172, #173,
#174 for T57's three parts. T58 and T59 follow once these land.

**Why M11 before M10.** The milestone order says dashboard then hardening, and
I am taking hardening first for two reasons. M10 needs a frontend stack this
project has never had and the spec does not choose — a decision above the
board. And T53, the dashboard's jobs view, is built on T57.3's SSE endpoint,
so doing T57 first unblocks M10 rather than delaying it.

`partial` has been waiting in `jobs/model.py` since M0 with a docstring saying
"derived at read time (T57)", and `canceled` has been in the schema since 0005
with nothing able to reach it. Two promises the code already makes.
| 175 | the job fan-out is unreachable; nothing creates a parent      | done      | high     | medium | 172             |
| 176 | convention — constructing the state proves only the reader    | done      | medium   | small  | 170, 171, 175   |
| 177 | rotate the master key, re-encrypting every secret (T59)      | done      | medium   | medium | 003, 004, 015   |
| 178 | dry-run a shared-resource edit; blast radius per tree (T58)   | done      | medium   | big    | 054, 064        |

## PO — M11's last two, 2026-09-26

T57 is complete (#172, #173, #174, plus #175 which made it reachable).

**#177 (T59, rotate-key) promoted.** One deviation decided in the ticket: the
spec says it returns a job id, and it will not. A job's `scope` is persisted,
so queueing a rotation writes both master keys into the database in plaintext
— the single thing this subsystem exists to prevent. Synchronous, one
transaction, and the reason is written down where the next person will find it.

**#178 (T58, dry-run) authored and PARKED as `big`.** Its impact half is real
work that is now possible — #064's signatures say what goes stale and #054 made
a tree's sources explicit. Its COST half has no source of truth: nothing
records tokens per job, so `tokens` and `usd` would be numbers we made up,
shown to an operator deciding whether to spend money. Omitting them is better
than inventing them, and the fix is a per-job cost record — which the spec's
own `cost` field on a job already implies and nobody has built.
| 179 | a job records the tokens it spent                             | done      | medium   | medium | 132, 133, 172   |

## PO — where the board stands, 2026-09-26

Every lane is empty. M9 (manual edits) and M11's authored work (T57 via
#172-#175, T59 via #177) are done, plus the multi-tree correction (#054, #166),
the read door (#168, #169), and three conventions now in a COMMITTED
`CONTRIBUTING.md` (#170, #171, #176).

**What remains, and what each needs:**

- **M10, the dashboard (T49-T56).** Eight tickets and a whole web surface. The
  spec says only "another client of the same API" and names no frontend stack;
  `CLAUDE.md`'s tech-stack section does not either. That is a stakeholder
  decision, not a board one. T53's SSE dependency is already built (#174), so
  nothing else blocks it.
- **#178 (T58, dry-run).** Parked on cost, and **unparked by #179**: a job now
  records its tokens, so an estimate has something to be estimated FROM. Its
  impact half was always ready. `big`, and worth splitting when it is picked
  up.
- **#051 (job DAG) and #077 (ANN shadow index).** DESIGN tickets that want a
  milestone. #077 wants a MEASUREMENT first — #168 showed what a real-size
  number is worth, and recall latency is exactly that kind of question.
- **Seven low items** (#042, #044, #046, #049, #050, #052, #056). Hygiene or
  YAGNI-gated. None degrades the product; I have left them deliberately at
  every triage and would again.
| 180 | the dashboard shell — server-rendered, logged in, role-gated | done      | medium   | medium | 006, 054, 139   |

## PO — M10 opens, 2026-09-27

**The stakeholder chose the stack: server-rendered, Jinja + HTMX.** No Node
toolchain and no build step, so the dashboard ships inside the one `hrono`
binary — which is what "one binary" has meant for every other surface. T50's
node graph will want a small vendored JS library; that is a smaller cost than a
second release artifact, and it is T50's to pay.

#180 is T49, the shell. Its one real question is how a BROWSER authenticates
against an API that takes a Bearer token, and the ticket settles it: the same
API token the CLI uses, in an HttpOnly SameSite=Strict cookie, resolved through
the SAME `require_role` machinery. A second auth path is how "roles enforced
server-side from day one" stops being true.
| 181 | the dashboard jobs view, live (T53)                           | done      | medium   | medium | 180, 172-174    |
| 182 | the dashboard topic page — brief, members, preview (T51)      | done      | medium   | medium | 180, 113, 129   |
| 183 | the dashboard node graph — lazy expand, health (T50.1/.2)     | done      | medium   | medium | 182, 064, 123   |
| 185 | the dashboard triage view — what needs attention (T52)        | done      | medium   | medium | 180, 182, 183   |
| 186 | the dashboard activity view — what the tree decided (T54)     | done      | medium   | small  | 180, 182        |
| 187 | the dashboard config tables, secrets masked (T55 part)        | done      | medium   | small  | 180, 054        |
| 184 | non-tree edges on the graph — pull, proximity (T50.3)        | done      | medium   | medium | 183, 089, 087   |
| 188 | edit a topic from its page — rename, brief, notes (T56 part)  | done      | medium   | medium | 182, 156, 157   |
| 189 | structure surgery from the page — merge, dissolve, split (T56) | done      | medium   | medium | 188, 158, 163   |
| 190 | dry-run a shared-resource edit — tree-keyed impact (T58)      | done      | medium   | big    | 054, 064, 179   |
| 191 | repointing a model at another upstream model invalidates nothing | done      | high     | medium | 064, 190        |
| 192 | the dry-run cost half — calls and tokens from history (T58)   | done        | medium   | medium | 190, 179        |
| 193 | measure what a recall actually costs                         | done      | medium   | small  | 075, 166        |
| 194 | score recall vector leg in numpy — the same math, 18x        | done      | medium   | medium | 193, 075        |
| 195 | split the dashboard module — 850 lines, 21 routes             | done      | low      | small  | 180, 189        |
| 196 | CI — run the gate on every push and pull request              | done      | high     | small  | -               |
| 197 | UX review — can a human actually use this?                    | done      | high     | medium | -               |
| 198 | a real-corpus build produced no clusters, once                | backlog   | high     | medium | 040             |
| 199 | a registry write that loads weights outruns the client        | backlog   | medium   | small  | 168             |
| 201 | a usage ledger — every model call recorded against its run | done | high | big | - |
| 202 | usage roll-ups — per run, per model, per user, with honest cost | done | high | medium | 201 |
| 203 | the dashboard shows what was spent — home, run page, a Usage page | todo | medium | medium | 202 |
| 204 | export compaction — any depth down to 3-4 hops, pages that stay readable | done | high | big | - |
| 205 | export from the panel — preview the shape, download the archive | done | high | medium | 204 |
| 206 | prove the export — a real agent answers real questions from the folder | todo | high | big | 204, 217 |
| 207 | ask a question in the panel — recall with its evidence | done | high | medium | - |
| 208 | find things — text search, an outline view, file to topic | todo | medium | medium | - |
| 209 | manage users in the panel — create, revoke, change role | todo | medium | medium | - |
| 210 | rebuild the Settings page — one collection at a time, forms a person can fill | todo | high | big | - |
| 211 | the Guide tells the truth and covers what people ask | todo | medium | medium | - |
| 212 | topics you can tell apart, and a map whose labels do not collide | done | high | big | - |
| 213 | a run page that says what happened, what failed, and lets you retry | todo | high | big | - |
| 214 | the topic page — sections you can tell apart, facts before hashes | todo | medium | medium | 212 |
| 215 | the shell and the home page — no overflow, no overlap, a home that answers "is it up to date" | todo | high | big | - |
| 216 | one vocabulary — every label, hint and message read as a person would say it | todo | medium | medium | - |
| 217 | a model's refusal or chatter is never stored as a good brief | done | blocker | big | - |
| 218 | fix what the health page shows, from the health page | todo | medium | medium | 216 |
| 219 | from an empty install to a built tree, in the panel | todo | medium | big | 210, 202 |
| 220 | remote embedding calls record the tokens the provider reports | todo | low | small | 201, 202 |
| 221 | a condensation that is the model talking back is never cached as one | todo | high | medium | 217 |
| 222 | the map at scale — overlays and names a person can read on 100+ topics | todo | medium | medium | 212 |

**2026-10-03 — requirements review and UI review.** #201-#219 come from
`REQUIREMENTS.md` (repo root, reviewed by the user) and
a UI review whose findings are written into the tickets themselves (screenshots in `ui-review-2026-10-03/`). Four groups:
usage and cost (#201-#203), export as a milestone (#204-#206), what the panel
lacks (#207-#209, #218, #219), and repairs to what is there (#210-#217).
#200 is not a ticket file; the number is already cited in code for user-driven
work, so authoring starts at #201. Scheduling was ruled out for now.
Suggested order: #217 first (the export's root page is a model refusal), then
#201 and #204 as the two milestone foundations, #215 and #210 for the UI.
