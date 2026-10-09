# Findings — hrono end-to-end manual QA, 2026-09-03

Severity: **blocker** (cannot use the feature) / **major** (works but wrong or
unreachable) / **minor** (papercut) / **note** (design observation).

Evidence paths are relative to `.e2e/`.

| # | sev | area | one line |
| --- | --- | --- | --- |
| F1 | major | llm | `claude-code` provider is accepted by the registry but no backend implements it |
| F2 | minor | api | registry create is `POST` only; `PUT` on a new name 404s, contradicting the documented "config is data you PUT" |
| F3 | minor | cli | bootstrap hint hardcodes `http://127.0.0.1:8080`, ignoring `--host/--port` |
| F4 | major | ingest | a supplied `filter.exclude` replaces the baked defaults instead of extending them |
| F5 | major | ingest | binary-ish text assets (SVG) are ingested and condensed — 8 sections of one logo |
| F6 | minor | ops | `serve` has no db-path flag; the database is always `./.hrono/hrono.db` |
| F7 | major | split | passages are packed to ~100 B, not the 800 B design budget (median 135 B) |
| F8 | minor | split | byte-chop cuts mid-token, producing meaningless passages like `'tColor = '` (9 B) |
| F9 | major | api | the whole M7 lifecycle (`update`, `propagate`, `monitor`, `repair`, `settle`) has no HTTP or CLI trigger |
| F10 | minor | cli | no CLI for `sources`/`connections`/`models`/`prompts`/`jobs` — config is curl-only |
| F11 | minor | api | query-param validation returns FastAPI's raw `{"detail":[...]}`, bypassing the `{error:{code,message,details}}` envelope |
| F12 | minor | recall | the z-score floor leaks hits for some off-topic questions instead of the explore message |
| F13 | major | jobs | one write from another process aborted an 11-minute job with `database is locked`; no BEGIN IMMEDIATE, no busy retry, no resume |
| F14 | minor | jobs | raw driver errors are stored and served verbatim, bypassing the error envelope |

---

## F1 — `claude-code` connection is accepted but unusable (major)

`src/hrono/registry/connections.py:56` defines `provider: Literal["claude-code"]`
with `auth.method: "none"`, so the connection stores and validates fine. But
`src/hrono/llm/client.py` is anthropic-SDK-only, and `grep -rn "claude-code"
src/` returns exactly one hit — that pydantic literal. A user can register a
`claude-code` connection, point a text model at it, and only discover at
`condense` time that nothing can call it. `connection_validation.py`
`_VALIDATORS` has no `claude-code` entry either, so `validate_connection`
silently returns.

Expected: either implement the backend (T44.2) or reject the provider at write
time with "provider not implemented yet".

This is what forced the harness in `scripts/claude_code_proxy.py` for this run.

## F2 — `PUT` cannot create a registry entry (minor)

`CLAUDE.md` and `implementation-notes.md` both say "config is data you PUT".
The engine (`src/hrono/registry/engine.py`) maps `POST /{collection}` to create
and `PUT /{collection}/{name}` to replace-only:

```
$ curl -X PUT /sources/tiny -d '{"name":"tiny","type":"git",...}'
{"error":{"code":"not-found","message":"sources not found: tiny","details":null}}   404
```

A PUT that creates-or-replaces is the idempotent shape the docs promise and the
one a config-as-data workflow (re-apply a whole file) needs.

## F3 — bootstrap hint prints the wrong port (minor)

Served with `--port 8299`, the first-run message says:

```
  hrono profile add local --server http://127.0.0.1:8080 --token <token>
```

`src/hrono/cli.py:_bootstrap_message` builds the hint from a literal, not from
the `host`/`port` the command was given. Copy-pasting it yields a profile that
cannot reach the server.

## F4 — `filter.exclude` replaces the defaults (major)

`src/hrono/ingest/filter.py:_excludes` returns the caller's list when present,
otherwise `_DEFAULT_EXCLUDE = ("**/node_modules/**", "**/*.lock")`. So a source
that excludes one directory silently loses `node_modules` and lockfile
protection — on a JS repo that is thousands of vendored files, embedded and
condensed at LLM cost.

In this run all three sources had to repeat both default patterns by hand:

```
"filter":{"exclude":["**/node_modules/**","**/*.lock","**/test/**","**/.github/**"]}
```

Expected: user patterns extend the defaults (with an explicit opt-out if
replacing is ever wanted).

## F5 — SVG and other binary-ish text assets are ingested (major)

The gate is a null-byte sniff, so PNGs are correctly skipped but SVGs sail
through and are treated as prose:

```
media/logo.svg                       -> 8 sections   (chalk)
docs/_static/itsdangerous-name.svg   -> 2 sections
docs/_static/itsdangerous-logo.svg   -> 1 section
docs/_static/itsdangerous-icon.svg   -> 1 section
```

Evidence: `artifacts/ingest-coverage.md`. That is 12 of 92 sections (13% of the
corpus, 13% of the condense LLM calls) spent on path data, and those sections
then join the clustering as noise. `constants.py` already carries an
extension -> category table; an `ignore` category (svg, eps, ico, map, min.js,
min.css, ...) is the natural fix.

## F6 — no way to point `serve` at a database (minor)

`DEFAULT_PATH = Path(".hrono/hrono.db")` and `serve` never overrides it, so the
database location is "whatever cwd the operator happened to be in". This run
had to `cd .e2e/run` first. `hrono reset` has the same constraint.

## F7 — passages are 8x smaller than the design budget (major)

Measured over the 92 real sections (`artifacts/ingest-coverage.md`):

```
passage bytes: n=1514 min=9 median=135 max=800 mean=183
histogram: <64: 7 | 64-200: 1151 | 200-400: 241 | 400-800: 112 | 800+: 3
```

76% of passages are under 200 B against an 800 B budget. Root cause is in
`src/hrono/ingest/split/pack.py:_pack`:

```python
limit = budget if min_group is None else min_group      # 100, not 800
...
if child.end - start >= limit:
    flush(child.end)                                    # flush at 100 B
```

`_passages` calls `_pack(wrapper, PASSAGE_BYTES, MIN_GROUP)`, so the flush
threshold becomes `MIN_GROUP = 100` and the 800 B budget only ever acts as an
upper bound for descending and chopping. Every group of siblings is cut as soon
as it crosses 100 bytes.

The settled recipe disagrees. `/Users/orest/repos/rad/hrono/app/structure-split.ipynb`
`pack_node` has **no min-group flush at all** — it flushes only when a group
would bust the budget — and its measured output is
`57 paragraphs, sizes [122, 195, ..., 799, 800, 835]`, i.e. a median in the
600s. The prose in `how-hrono-works.md` ("a sibling group is flushed once it
reaches 100 bytes, so a decent structural unit stands alone") was implemented
as an unconditional flush, which is not what the prototype does.

Concrete effect on a real docstring in `src/itsdangerous/signer.py` — seven
consecutive passages, each one line of one docstring:

```
  7  100B sp=/Signer/.block/.string/.string_content/.~blank-line
  8  284B sp=.../~blank-line[1]
  9  137B sp=.../~blank-line[2]
 10  115B ...
 11  132B ...
 12  144B ...
 13  111B ...
```

and the recall hit that comes out of it (`artifacts/recall-before-briefs.md`):

```
[source] .../signer.py sp:/Signer/.block/.string/.string_content/.~blank-line
"A signer securely signs bytes, then unsigns them to verify that     the value hasn't been changed."
```

The injection unit is a truncated sentence instead of the ~200-token unit the
design specifies, and the passage table is 4-6x larger than intended (1514 rows
for 92 sections), which inflates both the vector index and FTS.

## F8 — byte-chop cuts mid-token (minor)

The smallest passage in the corpus is 9 bytes: `b'tColor = '`, a fragment of an
identifier in `source/vendor/ansi-styles/index.d.ts`. `_chop` slices on raw
byte offsets with no attempt to back off to the nearest whitespace, and
`_merge_tiny` did not fold it because it is the first span of its group. It is
indexed in FTS and can be returned to an agent as a "passage".

## F9 — the incremental lifecycle has no trigger (major)

`update`, `propagate`, `monitor`, `repair`, `settle`, `cluster-briefs`,
`brief-upper` and every individual leaf op are registered in `OPS` and covered
by unit tests, but the only `enqueue` call site in the entire source tree is:

```
$ grep -rn "enqueue(" src/
src/hrono/server/trees.py:44:    job_id = enqueue(request.app.state.db, "maintain", {}, tree=name)
src/hrono/jobs/worker.py:23:def enqueue(
```

There is no `POST /jobs`, no `POST /trees/{name}/update`, and no `hrono jobs`
command, so hrono's differentiating feature is unreachable by any supported
interface. Nothing chains `update -> propagate -> monitor -> repair -> settle`
either, and `incubator.drain` / `incubator.age` have no production caller at
all (`grep -rn "incubator\." src/` -> only `placement.py` calling `park`).

This run had to insert job rows directly into the database
(`scripts/enqueue.py`) to exercise any of M7.

## F10 — no CLI for config or jobs (minor)

Shipped commands: `serve`, `recall`, `reset`, `profile {add,list,use,current,rm}`,
`admin reset-token`, `tree {maintain,export}`. The spec's `hrono sources`,
`hrono connections`, `hrono models`, `hrono prompts` and `hrono jobs` do not
exist, so registering a source or checking a job means hand-written curl.

## F11 — two different error envelopes (minor)

Body validation goes through the app envelope, query validation does not:

```
POST /sources {"name":"bad","type":"git"}
{"error":{"code":"validation-error","message":"invalid body","details":{"errors":[...]}}}   422

GET /trees/default/export?levels=abc
{"detail":[{"type":"int_parsing","loc":["query","levels"],...}]}                            422
```

A client cannot rely on one shape.

## F12 — off-topic questions sometimes still return hits (minor)

T27 says an empty result becomes the explore message. Three of five nonsense
questions did exactly that; two leaked (`artifacts/recall-before-briefs.md`):

```
"recipe for sourdough bread starter"            -> 0 hits, "no confident matches - explore the map."
"how to change a car tyre"                      -> 0 hits, explore message
"zzzzz qqqqq wwwww"                             -> 0 hits, explore message
"what is the capital of Peru"                   -> 0 hits, explore message
"quantum entanglement in banana futures"        -> 1 hit  (uuid/util.go randomBits)
"the mitochondria is the powerhouse of the cell"-> 3 hits (uuid/node.go ...)
```

The z-floor is relative to the corpus score distribution, so on a small corpus
a nonsense query can still produce an outlier. Worth re-checking the floor
against a corpus of this size, or adding an absolute similarity gate under the
z-gate.

---

## Verified working (no finding)

- **Byte-identity invariants hold on real repos.** 92 sections / 1514 passages:
  section == concat(passages) and file == concat(sections), 0 mismatches over 78
  files (`artifacts/reassembly-report.md`).
- **Budgets are respected as upper bounds**: 0 passages over 800 B, 0 sections
  over 10240 B.
- **Filter gates work**: `.github/**`, `tests/**`, `uv.lock` and both PNGs were
  correctly skipped; `py.typed` (empty) skipped.
- **Remote and local git sync both work**: `https://github.com/google/uuid`
  cloned and pinned at `2d3c2a9`, local clones pinned at their HEADs.
- **Secrets at rest**: the api key is Fernet ciphertext in `registry.config`
  (`gAAAAABqmaYGBg4...`), masked as `"***"` in responses; user tokens are stored
  as hashes; neither the master key nor any token appears in the server log.
- **Master-key refusals are clean and specific**: missing key, wrong key
  ("wrong master key: does not match the active key"), malformed key.
- **Role enforcement**: reader gets 200 on `GET /sources` and `POST recall`, 403
  on `POST /sources`, `POST /users`, `DELETE /users/{name}` and
  `POST /trees/{t}/maintain`; 401 for no token, garbage token, and a
  non-Bearer scheme; `bearer` in lowercase is accepted (RFC 7235).
- **Error paths**: unbuilt tree 404, duplicate name 409, unknown job 404,
  unreachable git url 400 ("cannot reach repository"), unknown source type 422
  with field details.
- **Registry validation really calls out**: the text-model write round-tripped
  through the LLM connection and the embedding-model write loaded MiniLM and
  checked the declared 384 dims (`logs/llm-calls.jsonl` entries 1-2).
- **Condensation quality is genuinely good** — see
  `artifacts/llm/call-0007.json`: verbatim identifiers, a real `GOTCHA:` line
  about UUIDv6 bitmasks.
- **Recall answers real questions well** even before any brief exists: all four
  on-topic probes returned the right file and the right function
  (`artifacts/recall-before-briefs.md`).

## F13 — one foreign write kills a long-running job (major)

`maintain` ran for 11m30s (57 of 92 condensations, ~7 min of paid LLM calls),
then died the instant a second process inserted a single row:

```
17:05:49  scripts/enqueue.py inserts one row into `jobs` (a `noop`)
17:05:50  maintain -> failed, error = "database is locked"
```

Job rows (`logs/api.log`, `GET /jobs`):

```
maintain failed | database is locked | 16:54:20 -> 17:05:50
noop  succeeded | None               | 17:05:49 -> 17:05:50
```

Three separate gaps behind this:

1. **"Single writer" is in-process only.** `db/database.py:Database.connect`
   guards one shared `sqlite3.Connection` with a `threading.Lock`. Nothing stops
   a second process — another `hrono serve`, a CLI, a backup script — from
   writing, and nothing tolerates it when it happens.
2. **No busy handling on the write path.** Writes go through
   `with database.connect() as conn, conn:` (e.g.
   `summarize/condense.py:59`), i.e. a Python-implicit DEFERRED transaction.
   A read-then-write transaction that loses its snapshot to another writer
   returns SQLITE_BUSY immediately and `PRAGMA busy_timeout=5000` does not
   retry it. `BEGIN IMMEDIATE` for write transactions plus an explicit
   retry/backoff on SQLITE_BUSY is the standard fix.
3. **No resume, no retry, no checkpoint.** The op is "atomic" in the sense that
   it fails whole; `maintain` restarts its stage chain from the beginning. Here
   the content-hash caches saved the expensive part (the 57 committed
   condensations were reused on the re-run), but nothing in the design says a
   90%-complete `condense` must not be lost — only the cache makes it survivable.

## F14 — raw driver errors leak into the job record (minor)

The failure above is stored and served verbatim as `"database is locked"`. Every
other surface routes through `AppError` and the `{error:{code,message,details}}`
envelope; the worker stores `str(exc)` from any exception, so a client sees the
sqlite driver's wording with no code to branch on and no hint that a retry is
the right response.

## F19 — `hrono tree export` cannot write a single file (major)

```
$ hrono tree export default -o exports/attempt1
refused to write outside exports/attempt1: '/benchmark-js-97.md'
$ echo $?
1
$ find exports/attempt1 -type f | wc -l
0
```

The server returns 93 of its 94 manifest paths with a **leading slash**
(`artifacts/export-manifest.txt`):

```
   1621B  /benchmark-js-97.md
   4570B  /brief.md
   ...
   1489B  root.md          <- the only relative one
```

`export/render.py:42-48` special-cases the root's own brief to `"root.md"` but
not the root's **sections**:

```python
directory = _directory(node_id, parent, conn)      # "" for a parentless node
path = "root.md" if node_id == tree.root else f"{directory}/brief.md"
...
files[f"{directory}/{name}.md"] = _section_markdown(conn, section_id)
```

With `directory == ""` every section path becomes `"/<name>.md"`. The CLI then
does `out / entry["path"]`, and pathlib discards the left side of a join with an
absolute path:

```
out / p         = /benchmark-js-97.md
(out/p).resolve = /benchmark-js-97.md
base            = /Users/orest/repos/hrono/.e2e/exports/attempt1
escapes base?   True
```

so the (correct) traversal guard added in #081 refuses the first entry and the
command aborts having written nothing. T32 is broken end to end for any tree
whose root carries sections directly. Two separate defects: the renderer must
not emit absolute paths, and `_materialize` should reject/normalise a leading
slash rather than let pathlib silently reroot it.

## F20 — export silently drops briefs when several nodes are parentless (major)

`export/store.py:load` picks the root with `root = max(node_level, key=...)`.
With 7 nodes all at level 0 that is an arbitrary node, and the other 6 have no
parent either, so `_directory` returns `""` for all of them and
`render.py:42` computes the same key for every one:

```python
path = "root.md" if node_id == tree.root else f"{directory}/brief.md"
#                                              ""      -> "/brief.md"
```

All six non-root briefs write to the single key `"/brief.md"` in the `files`
dict; the last one wins. The manifest contains exactly one `/brief.md` (4570 B,
the Go-uuid node's brief) and the other five briefs — chalk source,
itsdangerous docs, itsdangerous source, project config, licences — are **gone
from the export**, with no error.

The root brief is then also misleading: `root.md` presents one repo's brief as
the summary of a map that contains all three.

This is the same collision class that #095394ce fixed for sibling directory
names, reintroduced by the empty-directory case. Either `load` must refuse a
forest ("tree not built to a single root") or `_directory` must name every
top-level node.

## F21 — a garbage brief is stored with no guard (major)

Node 1 clustered the four SVG assets (see F5). Its brief, served verbatim to any
agent that reads the map (`artifacts/tree-01-after-build.md`):

```
This appears to be a condensation format guide with SVG examples, not a request
for me to act on something. Are you shar[ing]...
```

The model answered conversationally instead of summarising, and nothing caught
it: `briefs.unfaithful` is `[]` for this node, so the mechanical faithfulness
gate passed it. A brief that is a question back to the caller is not a summary,
and there is no shape check (no "is this a refusal/meta-response" guard, no
minimum-content check) between the LLM and the stored tree.

Junk input (F5) plus no output guard means the tree's first node is noise.

## F22 — the faithfulness gate false-positives on ordinary prose (minor)

`briefs.unfaithful` after the build (`artifacts/tree-01-after-build.md`):

| node | flagged tokens |
| --- | --- |
| 4 | `CI/CD`, `tabs/spaces/line` |
| 5 | `Signer.rsplit`, `TimedSerializer.loads`, `e.g` |
| 6 | `binaries/packages`, `licensor/contributors` |
| 7 | `encoding/decoding` |

`Signer.rsplit` is a genuine catch — the brief attributes a `str.rsplit` call to
the `Signer` API. The rest are not identifiers at all: the gate treats any token
containing `/` or `.` as an identifier needing source support, so `CI/CD`,
`e.g`, `encoding/decoding` and `licensor/contributors` are flagged as
unfaithful. Five false positives against one true positive on a 7-node corpus
makes the signal unusable as a triage queue.

## F23 — the server wedges permanently after a failed job: writes 500, reads go stale, the worker dies, `/health` still says ok (blocker)

The most serious finding of the run. After `maintain` #2 failed at 17:14:54
(F16), the server stayed up and kept answering `/health` with
`{"status":"ok"}` for the next 20 minutes while being completely broken.

**1. Reads serve a stale snapshot.** A job row written by another process at
17:20:11 is in the file but invisible to the server:

```
### direct read-only query (separate process):
jobs rows: 4
   ('job_3e4ef4b0...', 'maintain', 'failed')
   ('job_fed4e3e7...', 'noop',     'succeeded')
   ('job_c653aa8c...', 'maintain', 'failed')
   ('job_9ccb1d2a...', 'update',   'pending')      <-- written 17:20:11
sections: 99

### via the server API (GET /jobs):
jobs rows: 3
   job_3e4ef4b0... maintain failed
   job_fed4e3e7... noop     succeeded
   job_c653aa8c... maintain failed                 <-- the update job is missing
```

**2. Every write fails with a 500.**

```
$ ./scripts/api.sh POST /sources '{"name":"probe-after-stale",...}'
{"error":{"code":"internal-error","message":"internal error","details":null}}   500
```

`logs/02-serve.log:168-188`:

```
File "/Users/orest/repos/hrono/src/hrono/registry/engine.py", line 52, in create_item
File "/Users/orest/repos/hrono/src/hrono/registry/store.py", line 30, in insert
sqlite3.OperationalError: database is locked
```

**3. The worker stops working.** The `update` job sat `pending` for 10 minutes
and was never claimed — `claim_next` polls on the same stale connection, so it
cannot see pending work. Every subsequent job silently never runs.

**4. `/health` and the read endpoints keep reporting success**, so nothing
outside the process can tell. `GET /sources` and `POST recall` both returned
200 with (stale) data throughout.

Mechanism: `db/database.py` holds exactly one `sqlite3.Connection` for the
process lifetime, guarded by a `threading.Lock`, and writes ride Python's
implicit DEFERRED transaction (`with database.connect() as conn, conn:`). When
an exception escapes from inside one of those blocks, the connection is left in
an open transaction. In WAL mode that pins a read snapshot: reads keep returning
the old view, and any write from that connection conflicts with the newer WAL
content and returns SQLITE_BUSY ("database is locked"). Other processes are
unaffected — which is why the external insert succeeded while the server could
not see it.

Only a restart clears it. What is missing:

- an explicit `rollback()` on the shared connection whenever an op or request
  raises (a `try/except` around the yield in `Database.connect`)
- `BEGIN IMMEDIATE` for write transactions plus retry on SQLITE_BUSY (also F13)
- a `/health` that actually probes the database (`SELECT 1` plus
  `connection.in_transaction`) instead of returning a constant
- per-request/per-op connections, or a pool, so one poisoned connection is not
  the whole server

## F24 — an unsupervised worker thread dies silently, stranding the job (blocker)

`jobs/worker.py`:

```python
def _execute(self, job):
    try:
        handler(job, JobContext(self._database, self._cipher))
    except Exception as exc:
        self._finish(job, "failed", str(exc))     # <- this call is NOT guarded
    else:
        self._finish(job, "succeeded", None)

def _finish(self, job, status, error):
    with self._database.connect() as conn:
        store.set_status(conn, job.id, status, error, _now())
```

`_finish` writes. When the connection is wedged (F23) that write raises, the
exception escapes `_execute`, escapes `run()`, and the daemon thread ends. There
is no supervisor, no restart, and no log line — `grep "Exception in thread"` on
the server log finds nothing.

Observed: `propagate` was claimed at 17:33:16, and 10 minutes later:

```
$ python scripts/enqueue.py ... noop     -> job_d3371de2...
20:44:19 [('propagate', 'running'), ('noop', 'pending')]
20:44:24 [('propagate', 'running'), ('noop', 'pending')]
20:44:29 [('propagate', 'running'), ('noop', 'pending')]
20:44:34 [('propagate', 'running'), ('noop', 'pending')]
```

`propagate` is stranded `running` for ever (nothing reclaims a job whose worker
died), the new `noop` is never claimed, and the API keeps answering reads. The
run had to abandon the queue entirely and drive ops in-process
(`scripts/drive_op.py`) to finish the M7 scenarios.

Needed: guard `_finish` and `_claim`, restart the thread on failure (or run the
loop under a supervisor), log any unhandled worker exception, and reclaim jobs
left `running` with no live worker (a heartbeat or a startup sweep).

## F25 — the sync cache is cwd-relative, so one database can have several divergent caches (major)

`ingest/sync.py:24` and `ingest/split_op.py:36` both hardcode
`_CACHE_ROOT = Path(".hrono/cache/sources")` — resolved against the **current
working directory**, not against the database. The server ran with cwd
`.e2e/run`; the in-process op driver ran with cwd `.e2e`. Result:

```
$ find . -maxdepth 4 -type d -name sources
./.hrono/cache/sources          <- driver's cache
./run/.hrono/cache/sources      <- server's cache

  run/.hrono/cache/sources/itsdangerous -> 84a036f   license.rst present
      .hrono/cache/sources/itsdangerous -> 506eb72   license.rst absent
  run/.hrono/cache/sources/chalk        -> 661317e   utilities.js present
      .hrono/cache/sources/chalk        -> bce99a4   utilities.js absent
```

Two clones of every source for one database, three commits apart. Diffing the
same database against the stale one invents changes, including a **reversed
rename**:

```
## server cache
- chalk:        moved  source/utilities.js  (was source/util-helpers.js)
- itsdangerous: changed src/itsdangerous/signer.py
                new     docs/license.rst          <- deleted two commits ago
## driver cache
- chalk:        0 changes
- itsdangerous: 1 change
```

So `hrono serve` started from a different directory silently re-clones every
source and can undo the last update's classifications. The cache must hang off
the database's own directory (or a configured data root), never off cwd.

## F26 — an empty file is a phantom change on every single run (major)

`src/itsdangerous/py.typed` is 0 bytes. The filter admits it (size under the
cap, no null byte), but `split.split()` returns `()` for empty input, so no
section is ever stored — and `diff` therefore classifies it `new` **every
time**:

```
## driver cache, repos untouched since the last update
- itsdangerous: 1 changes
    new      src/itsdangerous/py.typed
- .../py.typed: exists=True size=0 bytes
- stored sections for it: 0
```

This is why an `update` over an unchanged corpus is never a no-op:

```
before (sections node_members embeddings pending batch): 101 92 1792 2 5
update -> succeeded in 0.7s
after  (sections node_members embeddings pending batch): 101 92 1792 2 6
# two more no-change runs -> batch 8
```

Every run re-syncs, re-diffs, re-reconciles and bumps `tree_batch.batch`. The
batch counter drives incubator aging (`current_batch - batch > MAX_AGE`), so
phantom work ages real pending chunks toward forced assignment. Any file the
splitter yields nothing for (empty, or whitespace-only) has this behaviour.

Fix candidates: skip zero-byte files in the filter, or record a
zero-section marker for a file that produced no sections so `diff` knows it was
seen.

## F27 — a pure rename ejects the file from its topic (major)

`git mv source/utilities.js source/util-helpers.js`, content byte-identical,
then `update`:

```
  embeddings before: 1791
  embeddings after:  1792        (content NOT re-embedded; +1 is the new path string)
  old path rows: 0 | new path rows: 1
  section 196 source/util-helpers.js -> node None
  pending: {'path': 'source/util-helpers.js', 'batch': 4}
```

The content vector was correctly reused (T34.3's "reuse content vec" holds), but
the section did not stay in node 2 — it was **parked in the incubator**. The
path-blend (alpha 0.5) means a renamed file's combined vector moves by half its
norm, which dropped its similarity to its own cluster's centroid below TAU 0.70,
and generic placement then treated it as homeless.

`update` never uses the `moved` classification for placement: `diff` produces
it and `reconcile` consumes it for content reuse, but `placement.place` sees only
a delta and re-scores it. T34.3 specifies moved/renamed handled **in place** —
a rename should keep its membership and simply re-stamp the path, since the
content that defines the topic did not change.

## F28 — warm-init is silently disabled after any incremental update (major)

T39.2 specifies settle rebuilds with `init = stored coords`. But
`placement.place` never writes `section_coords` for a section it places, so
after one update the table no longer covers the membership:

```
 members: 92   coords: 89
 members with no coord: 3
 their paths: ['src/itsdangerous/rotation.py',
               'src/itsdangerous/signer.py', 'src/itsdangerous/signer.py']
```

`cluster/store.py:stored_coords` then returns `None` (correctly — a partial set
cannot align), so `settle` cold-inits UMAP. Since settle only ever runs *because*
churn accumulated, and churn means sections were placed without coords, the warm
path can never fire in practice. The whole point of warm init — a stable
embedding across rebuilds so unchanged content keeps its position, and node
signatures keep matching — is lost.

Fix: have `placement.place` store the reduced coordinate it implicitly assigns
(or accept a partial init, filling missing rows from their nearest placed
neighbour) so warm init survives an update.

## F29 — the incubator is a black hole: nothing drains it, ever (blocker)

```
$ grep -rn "incubator" src/ | grep -v incubator.py
src/hrono/cluster/placement.py:29:from hrono.cluster import incubator, store
src/hrono/cluster/placement.py:172:    incubator.park(conn, tree, content_hash, path, batch)
```

`park` is the only production call. `incubator.drain` and `incubator.age` — the
functions that turn a pending pool into real clusters or force-assign an aged
chunk — have **no caller anywhere** in `src/`. `update`, `propagate`,
`monitor`, `repair` and `settle` all ignore the pool.

State after this run's scenarios:

```
pending: [('docs/unrelated-cooking-notes.md', batch 1),
          ('source/util-helpers.js',          batch 4)]
tree_batch: batch 8
```

Both chunks are in **no node**, so they appear in no brief, no upper level and
no export — they are silently absent from the knowledge base, though recall can
still return their raw passages. One of them (`util-helpers.js`) was a *member
of node 2* before it was renamed (F27), so the incubator turned a working
membership into permanent limbo.

Combined with F17 (the drain would crash even if it were called), the incubator
is non-functional end to end: chunks go in and never come out.

## F30 — recall returns the brief's URI footer as its best "summary" answer (major)

The five top hits for *"how do I set the color level in chalk"* are all `summary`
kind, all from node 2's brief — and every one of them is a slice of the
mechanical reference list the `brief` op appends, not the summary text:

```
--- hit 1 [summary] '- git:///.../chalk/source/vendor/supports-color/index.d.ts@661317e...'
--- hit 2 [summary] '- git:///.../chalk/source/vendor/supports-color/index.js@661317e...'
--- hit 3 [summary] '- git:///.../chalk/source/vendor/supports-color/browser.d.ts@661317e...'
--- hit 4 [summary] '- git:///.../chalk/source/vendor/supports-color/browser.js@661317e...'
--- hit 5 [summary] '- git:///.../chalk/source/vendor/ansi-styles/index.d.ts@661317e...'
```

`summarize/brief.py` bakes member URIs into `text` via `_references(uris)`, and
`#071` then splits the whole brief — footer included — into `node://` passages
that go into both the vector index and FTS. The footer is a wall of paths, so it
matches any query whose words appear in a filename (here "color" via
`supports-color`), and it scores well because a path list is lexically dense.

An agent asking a real question gets five lines of URIs injected into its
context and none of the brief's actual prose. The reference block should be
excluded from the passage split, or stored as metadata rather than inside
`briefs.text`.

## F31 — no per-document diversity in the result window (major)

```
"how do I set the color level in chalk"      limit=10 -> 10 hits from 4 distinct documents
"how is key rotation handled"                limit=10 -> 10 hits from 4 distinct documents
"how does the signer verify a signature"     limit=10 -> 10 hits from 2 distinct documents
```

RRF fusion caps the result count but never dedupes or diversifies by source
document, so one file (or one brief) can occupy the entire window — 5 of 5 in
the chalk case, 8 of 10 elsewhere. Combined with F7's ~135 B passages, a single
document trivially supplies ten neighbouring fragments that all score alike.

For a fixed agent context budget this is the difference between ten views of one
file and a survey of the corpus. A per-document cap (or MMR-style
diversification) in the fusion step is the standard fix.

## F32 — `hrono reset` leaves the source cache behind (minor)

The command's own help says it destroys "users, registries (with their encrypted
secrets), jobs, and ingested content". It removes the three database files and
leaves the clones:

```
$ hrono reset --force
Removed:
  .hrono/hrono.db
  .hrono/hrono.db-wal
  .hrono/hrono.db-shm
$ ls -la .hrono
drwxr-xr-x  cache          <- 10 MB of cloned sources, still there
```

So a "fresh start" begins with orphaned clones of sources that no longer exist
in the registry, and `sync` will diff against them. With F25 (the cache is
cwd-relative) the operator has no reliable way to know which cache a given
database is even paired with. Either delete the cache too, or state that it is
kept.

## F33 — the judge verdict is parsed by substring, and the model does not obey the one-word instruction (major)

The judge prompt says *"Reply with exactly one word: 'none' / 'minor' /
'major'"*. Of the four judge calls this run made, **two ignored it**
(`artifacts/llm/call-0108.json`, `call-0109.json`):

```
call 107: 'none'
call 108: "minor\n\nThe removal of `as name` aliasing in the imports is a type-checking and IDE-visibility change, not a functional one..."
call 109: "minor\n\nThe summary accurately captures the library's architecture... but the source no longer uses `as name` aliasing..."
call 110: 'none'
```

`summarize/propagate.py:_verdict` classifies by substring over the whole reply:

```python
def _verdict(text: str) -> str:
    lowered = text.lower()
    if "major" in lowered:
        return "major"
    if "minor" in lowered:
        return "minor"
    return "none"
```

Given that the model demonstrably explains itself half the time, and that the
prompt's own vocabulary ("major", "minor") is exactly what an explanation
repeats, this misclassifies predictably: *"none — this is not a major change"*
scores **major**, and "major" is checked first so *"minor, certainly not
major"* also scores major. A false `major` climbs the cascade and marks
ancestors stale (and at scale, forces a settle).

Parse the first token, or require an exact match and retry/abstain otherwise.

Side observation worth confirming: four provider calls were made for a
`BEST_OF = 3` panel on a single topic (all four with identical
`content_chars=18731`), so either the SDK retried transparently or the panel
runs one extra call — cost accounting for `propagate` is not exactly 3x.


---

# Follow-up findings, same run (formerly the repository's root FINDINGS.md)


## F15 — the baked UMAP recipe cannot handle fewer than 27 inputs (blocker)

Measured against the real `_default_reduce` (`artifacts/umap-threshold.md`):

| N vectors | outcome |
| --- | --- |
| 5, 7, 10, 15, 20, 25, 26 | `TypeError: Cannot use scipy.linalg.eigh for sparse A with k >= N` |
| 27, 28, 30, 40 | ok -> shape (N, 25) |

`UMAP_DIMS = 25` means spectral init asks for `k = n_components + 1 = 26`
eigenvectors, which requires `N > 26`. So **any level with fewer than 27
vectors crashes**, and it crashes with a `TypeError` from scipy — not with
`ClusterError`.

Three call sites are affected:

1. `cluster` (leaf build) — a corpus of fewer than 27 sections cannot be
   clustered at all. A small repo is unusable.
2. `build-tree` -> `cluster_briefs` — see F16.
3. `incubator.drain` -> `core_labels` — see F17.

The fix belongs in one place: guard `_default_reduce` on
`len(vectors) <= UMAP_DIMS + 1` and either lower `n_components` for the small
case, use `init="random"` (which skips the spectral solve), or raise
`ClusterError` so the callers' existing guards fire.

## F16 — `build-tree` crashes instead of stopping, so no tree reaches root (blocker)

Observed on this run's real corpus. `maintain` completed 92 condensations, built
7 leaf nodes and 7 briefs, then died:

```
$ ./scripts/api.sh GET /jobs/job_c653aa8c4d8b42d498c73f65a69f3d29
{"op":"maintain","status":"failed",
 "error":"Cannot use scipy.linalg.eigh for sparse A with k >= N. Use scipy.linalg.eigh(A.toarray()) or reduce k.",
 "created_at":"2026-09-03T17:07:04Z","updated_at":"2026-09-03T17:14:54Z"}
```

`summarize/build_tree.py` documents this exact situation as handled:

```python
try:
    cluster_briefs(...)
except ClusterError:
    break  # too sparse to cluster near the root -> current top is root
```

but the real failure is a `TypeError` from scipy (F15), so the guard never
fires, `_collect_root` is never reached, and the tree is left with level 0 only:

```
nodes 7 | node_children 0 | briefs 7 | levels [(0, 7)]
```

Consequences, all confirmed:

- there is no root, so `GET /trees/default/export` returns
  `404 {"error":{"code":"not-found","message":"tree not built: default"}}` —
  the M6 MVP deliverable is unreachable for this corpus
- `hrono tree export` therefore cannot produce anything
- `maintain` reports `failed`, so the second `embed` pass for brief passages
  (the last line of the op) never runs either

A corpus needs >= 27 leaf nodes — at `min_cluster_size=5`, roughly 135+
well-separated sections — before `build-tree` can even attempt level 1. Three
real repos (790 KB, 92 sections) are not enough.

## F17 — the incubator drain gate is 5 but its clusterer needs 27 (major)

```python
if len(ready) < MIN_CLUSTER_SIZE:      # 5
    return False
...
labels = labeler([v for _, _, v in ready])    # -> core_labels -> _default_reduce
```

`cluster/incubator.py:drain` decides the pool is "full enough" at 5 chunks and
then calls the UMAP recipe, which needs 27 (F15). Every drain of a pool holding
5-26 chunks raises `TypeError`. Since the incubator exists precisely to hold
small numbers of chunks until siblings arrive, this is the common case, not the
edge case.

## F18 — no test exercises the real clustering recipe at small N (note, QA gap)

Every affected path is tested only through an injected seam:
`tests/summarize/test_build_tree.py:156` passes `build=build`,
`tests/cluster/test_levels.py` likewise, and `incubator.drain` takes a
`core_labeler` override. The one test that runs the real recipe
(`tests/cluster/harness.py:planted_groups`) defaults to
`groups=5, per_group=14, noise=6` = **76 vectors**, comfortably above the
threshold. So 585 green tests coexist with a corpus size that cannot build.

Suggested regression teeth: call `build_clusters` and `core_labels` with
N = 4, 10, 26, 27 and assert a clean `ClusterError` (or a successful reduce),
never a driver exception.
