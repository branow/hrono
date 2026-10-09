# hrono — implementation notes

Working notes for the actual build. Grows as we settle decisions. Right now: the REST API spec.

## Shape (settled)

- One binary, `hrono`, subcommands. Server is just one subcommand.
- `hrono serve` — long-running HTTP server on a port (e.g. 8080). Owns the SQLite file (single writer), all compute, all LLM calls. Home for background workers.
- Client subcommands (`hrono recall`, `hrono export`, …) are thin HTTP clients of that server. Web UI later is another client of the same API.
- Config is data you PUT; work is a job you POST. Writing config never triggers work as a side effect.
- Slow operations return a job id and run async on a background worker. `recall` is the one fast synchronous endpoint.
- API runs over HTTPS; secrets travel inline in request bodies. GET masks/omits secrets (write-only).
- `GET /health`, `GET /version` — unauthenticated liveness/version.

## Auth (minimal v1, roles present from day one)

Users authenticate with an API token (`Authorization: Bearer <token>`). Roles: `reader` (recall, GET), `writer` (edit config, run ops), `admin` (users, rotate-key, delete). Tokens are verify-only, so store a hash (not reversible-encrypted like provider secrets); compare on each request. Bootstrap: first `serve` with no users mints an admin token and prints it once.

```
GET/POST        /users            list ; create (admin) -> returns token once, never again
GET/DELETE      /users/<name>     read ; delete (admin)
{ "name": "alice", "role": "writer" }
```

## Secrets at rest

Secrets encrypted with a master key given to the server at startup (`hrono serve --key-file <path>`, preferred, or `HRONO_MASTER_KEY`); required or the server refuses to start. Key never stored in the DB (only ciphertext is). Use a vetted lib (Fernet / libsodium), never hand-rolled. Covers a stolen DB file; not a compromised host. Lost key = re-register sources.

Each secret-bearing row references the key that encrypted it, so a wrong/rotated key gives a clear per-record error instead of a silent failure:

```
keys(key_id, key_hash)             # key_hash = fingerprint, never the key
<secret row>.key_id                # which key encrypted this row
```

### admin: rotate master key

Admin-only, run as a job (touches every secret: decrypt-old / encrypt-new / bump key_id). Requires the old key as proof-of-possession — verified before anything runs, 403 on mismatch. After it completes, update the key file so the next restart uses the new key.

```
POST /admin/rotate-key { "old_key": "...", "new_key": "..." }   # returns a job id
```

## REST API

### shared-resource edits (applies to sources, connections, models, prompts)

These registries are referenced by name by multiple trees, so editing one has cross-tree blast radius. Rule, stated once:

- Resources are mutable — edit in place, no version-and-repoint. `?dry_run=true` is the safety.
- `PUT|PATCH /<collection>/<name>?dry_run=true` applies nothing; returns tree-keyed impact + estimated cost: `{ "affected_trees": [ { "tree": "...", "stale": {...}, "estimated_cost": {"usd": n} } ] }`.
- A real edit propagates staleness by name to every referencing tree's entities (a prompt edit invalidates exactly what that prompt produced; a model edit invalidates its role's outputs). Nothing re-runs automatically.
- Source config edit != source content change: auth-only edit = no staleness (same bytes); url/scope edit = content changes, referencing trees go stale on next `sync`. Actual content drift is not an edit, it's the `sync` op.

### sources/ — registry of places to pull data from

Pure declarative config. Registering does not pull anything. On write (POST/PUT), run a quick validation that we can actually reach + auth the source (git: reachable + creds work; workspace/confluence/notion: API auth works). Reject the write if it fails, so no dead source gets registered.

```
GET    /sources                list
POST   /sources                register one
GET    /sources/<name>         fetch
PUT    /sources/<name>         replace
DELETE /sources/<name>

# body — single git repo
{
  "name": "webphone",
  "type": "git",               # later: contentful, confluence, ...
  "url": "https://github.com/acme/webphone",
  "auth": { "method": "none" },       # or {"method":"token","token":"..."} / {"method":"ssh","key":"..."}
  "filter": {                         # optional, file-type sources only; baked defaults when omitted
    "exclude": ["**/node_modules/**", "**/*.lock"],   # globs (Path.full_match)
    "max_size_mb": 2                  # + null-byte sniff for anything no pattern caught
  }
}

# body — discovery source: enumerates many repos via provider API.
# Each discovered repo still gets a git://<host>/<owner>/<repo> identity; discovery
# is only how repos are found, never their address. Full re-discovery on each sync (v1).
{
  "name": "acme-bb",
  "type": "bitbucket-workspace",      # or "github-user"
  "owner": "acme",                    # workspace slug (bitbucket) / username (github)
  "auth": { "method": "token", "token": "..." },
  "include": ["*"],                   # optional repo-name globs
  "exclude": ["*-archive"]
}

# body — page/doc source with a scope selector.
# scope is a list of typed selectors, unioned; {"type":"all"} or empty = everything.
# Same selector idea generalizes across sources (space/page for confluence,
# page/database/workspace for notion, repo/owner for git discovery).
{
  "name": "eng-wiki",
  "type": "confluence",               # or "notion"
  "base_url": "https://acme.atlassian.net/wiki",
  "auth": { "method": "basic", "email": "...", "token": "..." },
  "scope": [
    { "type": "space", "key": "ENG" },
    { "type": "page", "id": "12345" }
  ]
}

# body — notion. API-only (no clone). Integration token (bearer). An integration
# only sees pages explicitly shared with it, so {"type":"all"} = everything shared
# with this token (via the search endpoint). No base_url (always api.notion.com).
# Identity: notion://<workspace>/<page-id>@<last_edited_time>.
{
  "name": "product-notion",
  "type": "notion",
  "auth": { "method": "token", "token": "ntn_..." },
  "scope": [
    { "type": "page", "id": "..." },
    { "type": "database", "id": "..." }
  ]
}
```

Naming rule: field keys snake_case, enum/type values kebab-case.

git clone with a token uses `x-token-auth` (access token, username-free): `https://x-token-auth:<token>@bitbucket.org/<ws>/<repo>.git`, `https://x-access-token:<token>@github.com/<owner>/<repo>.git`.

### connections/ — provider credentials (generic, one per provider account)

Not scoped to LLM vs embedding — the same account can serve both. Secrets never returned on GET (masked/omitted). On write (POST/PUT), run a quick validation with no inference cost: api-key providers hit the list-models endpoint (`GET /v1/models`, 200 = valid); claude-code checks the CLI is installed and logged in. Reject the write if it fails, so no dead connection gets registered.

```
GET    /connections            list
POST   /connections            register one
GET    /connections/<name>     fetch (secrets masked)
PUT    /connections/<name>     replace
DELETE /connections/<name>

# body — same tagged auth shape as sources; inline value, encrypted at rest.
# v1 providers: anthropic, openai, claude-code, openai-compatible (local LLM
# servers: ollama/vllm/lm-studio; endpoint set, auth usually {"method":"none"}).
{
  "name": "anthropic-main",
  "provider": "anthropic",
  "auth": { "method": "api-key", "key": "sk-ant-..." },
  "endpoint": null             # optional override for self-hosted/proxy
}

# openai — identical shape
{ "name": "openai-main", "provider": "openai",
  "auth": { "method": "api-key", "key": "sk-..." } }

# claude-code — no key; rides the claude CLI session already logged in on the
# server. Requires the claude CLI installed + authed on that machine; nothing passed.
{ "name": "cc", "provider": "claude-code",
  "auth": { "method": "none" } }
```

### models/ — usage config for a model (text or embedding)

One collection; `kind` discriminates. Same shape for both because they only differ by output type. `connection` null = load & run locally in-process (transformers / sentence-transformers); `connection` set = reach it over HTTP. Features reference models by name into typed slots; the server checks `kind` matches the slot (an embedding slot rejects a `text` model and vice versa).

```
GET    /models                 list
POST   /models                 register one
GET    /models/<name>          fetch
PUT    /models/<name>          replace
DELETE /models/<name>

# text model, remote
{
  "name": "cheap",
  "kind": "text",              # text | embedding
  "connection": "anthropic-main",   # null = in-process; set = over HTTP
  "model": "claude-haiku-4-5",
  "params": { "temperature": 0, "max_tokens": 4096 }
}

# embedding model, in-process
{
  "name": "local-qwen",
  "kind": "embedding",
  "connection": null,
  "model": "Qwen/Qwen3-Embedding-0.6B",
  "params": { "dims": 1024, "batch_size": 32 }
}
```

### prompts/ — registry of prompt templates

Ships defaults (seeded on first run); user can override a default or add named variants. A tree references prompts by name into typed slots, like models. `role` fixes which pipeline slot a prompt can fill; the server checks it matches the slot.

```
GET/POST              /prompts          list ; create
GET/PUT/DELETE        /prompts/<name>   read ; edit/override ; delete (defaults reset, not removed)

{ "name": "condense-default",
  "role": "condense",      # condense | brief | brief-upper | judge
  "template": "..." }      # prompt text with placeholders
```

### trees/ — the knowledge-tree feature

Build is recursive (cluster -> brief -> embed briefs -> cluster next level -> ... to root), so `embed`/`cluster`/`brief` recur per level; no fixed-stage model. Rules: status lives on entities (each section/node carries its own); an op is `(op, scope)`, scope defaults to everything that needs it; jobs are atomic (an op fans out into one atomic job per item, failures leave the rest pending); config edits mark affected entities stale, never auto-run. Two granularities of leaf entity: **sections** (~10 KB, clustering/traversal unit) and **passages** (~800 B, recall injection unit); a section reassembles byte-identically from its passages.

```
GET/POST                /trees                 list ; create (config only, builds nothing)
GET/PUT/PATCH/DELETE    /trees/<name>          read (config + health) ; edit -> recompute staleness
POST                    /trees/<name>/maintain -> {job_id}  easy button: run all ops in order, recursing
POST                    /trees/<name>/ops/<op> -> {job_id}  one op over an optional scope
GET                     /trees/<name>/export?levels=N        rendered agent-facing MD tree (see below)
GET                     /trees/<name>/sections , /passages , /nodes , /incubator   list/inspect entities
GET                     /trees/<name>/sections/<id> , /nodes/<id>                  one entity (inspect content)
```

Config body (PUT same shape; `name` is just a label). Operating constants (TAU 0.70, MAX_CAP 30, D_MAX 5, min_cluster_size 5, alpha 0.5, UMAP 25-dim, misfit thresholds) are **baked from the experiments**, not config — see clustering-lifecycle.md:

```
{ "name": "backend", "sources": ["webphone"],
  "models":  { "condense": "cheap", "brief": "smart", "judge": "cheap" },
  "prompts": { "condense": "condense-default", "brief": "brief-default",
               "brief_upper": "brief-upper-default", "judge": "judge-default" },
  "embedding": "local-qwen",
  "split":   { "code_kb": 10, "docs_kb": 10, "data_kb": 2 } }
```

Config edit dry-run: `PUT|PATCH /trees/<name>?dry_run=true` — same body, applies nothing, returns the impact (what goes stale, what would rebuild, estimated cost):

```
{ "stale": { "sections": 0, "nodes": 47, "levels": [1,2,3] },
  "ops": ["cluster", "brief"],
  "estimated_cost": { "condense_calls": 0, "brief_calls": 47, "tokens": 210000, "usd": 0.6 } }
```

`GET /trees/<name>` health summary:

```
{ "sources": [{"name":"webphone","synced_version":"a1b2","status":"fresh"}],
  "sections": { "total": 1240, "embedded": 1240, "pending": 0 },
  "tree": { "levels": 3, "nodes": 47, "briefs": {"fresh":44,"stale":3},
            "incubator": 5, "churn_since_settle": 0.02 } }
```

Ops + scope. Omit scope = everything that needs it (= resume). `op`, in a normal update's order:

- `sync` — pull source(s), detect + record the diff (new/changed/deleted/moved). Places nothing.
- `split` — re-split changed/new files into sections + passages.
- `embed` — embed content hashes missing a vector (sections and briefs).
- `cluster` — place sections into topics (empty tree = full UMAP/HDBSCAN build; incremental = sticky re-check + nearest-centroid placement + incubator drain).
- `propagate` — judge cascade: judge each changed topic's source diff vs its stored brief, mark ancestor briefs stale none/minor/major, write update_log. Marks only; regenerates nothing.
- `brief` — regenerate stale briefs (condense changed sections + write brief). Membership changes mark briefs stale directly, bypassing the judge.
- lifecycle: `monitor` (misfit rate) · `repair` (split oversized / migrate misfits / dissolve) · `settle` (warm rebuild + diff). Manual in v1.

```
{ "scope": { "type": "all" } }                    # source|section|node|level also
{ "scope": { "type": "source", "name": "webphone" } }
{ "scope": { "type": "node",   "id": "node_9" } }
```

Manual adjustments (admin-gated; what the dashboard drives). **A hand-edit pins the entity, and the pipeline treats a pin as a hard constraint** — a pinned brief survives `brief` regen; a pinned membership/parenting survives `settle`'s re-cluster (honored as fixed, never reshuffled). `unpin` hands it back to automation. Without this, a manual fix gets silently reverted on the next update.

```
PATCH /trees/<name>/nodes/<id>              { "title": "..." }        rename a topic
PUT   /trees/<name>/nodes/<id>/brief        { "text": "..." }         override brief (pins)
POST  /trees/<name>/nodes/<id>/unpin                                  release the lock
POST  /trees/<name>/nodes/<id>/reparent     { "to": "<node>" }        move a node under another parent (pins)
POST  /trees/<name>/nodes/merge             { "ids": [...] }          merge topics
POST  /trees/<name>/nodes/<id>/split                                  manual split (scoped mini-pipeline)
POST  /trees/<name>/nodes/<id>/dissolve                               remove topic; members re-place
POST  /trees/<name>/sections/<id>/move      { "to_node": "..." }      re-place a section (pins)
POST  /trees/<name>/{nodes|sections}/<id>/notes  { "text": "..." }    human annotation, export-visible
```

Notes are **export-visible**: a human "deprecated, use X" annotation flows into the rendered tree so the traversing agent sees it.

Export: `GET /trees/<name>/export?levels=N` renders the stored tree into the flat agent-facing MD tree (stored levels collapsed to N agent-facing levels, narrow-at-root/wide-at-leaves, mechanical child listings, Caution sections). v1 returns one MD document in the response body; partial/streamed download deferred.

### jobs/ — every async operation

Leaves are atomic; parents aggregate children (status/progress/cost derived, never written directly). Cancel is cooperative: stops scheduling new leaves and signals running ones; finished atomic work stays done.

```
GET   /jobs                 list (filter: tree, op, status, parent)
GET   /jobs/<id>            one job
GET   /jobs/<id>/children   child jobs
GET   /jobs/<id>/events     live progress via SSE (text/event-stream); one-way, so SSE not WebSocket
POST  /jobs/<id>/cancel     request cancel (cascades to pending/running children)

{ "id": "job_42", "parent_id": null, "tree": "backend", "op": "maintain",
  "scope": { "type": "all" },
  "status": "partial",     # leaf: pending|running|succeeded|failed|canceled; parent adds partial
  "progress": { "done": 1180, "total": 1240 },
  "cost": { "tokens": 480000, "usd": 1.12 },
  "started_at": "...", "finished_at": null, "error": null }
```

### recall — synchronous query (per tree)

The one non-job endpoint; fast by design. Engine is the frozen recipe (vector z-floor + BM25 + RRF fusion, cap, empty->explore); none of it leaks into the API.

```
POST /trees/<name>/recall   { "question": "...", "limit": 10 }   # limit optional, default 10

{ "hits": [
    { "kind": "source",     # source | summary
      "address": "git://github.com/acme/webphone/src/ContactService.java@1a2b",
      "sp_paths": ["sp:/ContactService/.class_body/getByUser"],
      "body": "…passage…", "score": 0.87 } ],
  "message": null }         # "no confident matches — explore the map." when hits is empty
```

## Client (hrono CLI)

Thin HTTP client of one server; no data or compute of its own. Every command runs against the **current profile**.

### Profiles (kubectl/gh call this a context)

A profile = `{name, server_url, token, default_tree?}`, stored in `~/.hrono/config.toml` under `[profiles]`. Switch freely between servers. (Renamed from "context" — that word is overloaded in a knowledge-base product: LLM context, the knowledge tree, the dashboard's context/tree switcher.)

```
hrono profile add <name> --server <url> --token <t>   register a profile
hrono profile list                                    list; marks the current one
hrono profile use <name>                              switch current
hrono profile current                                 show current
hrono profile rm <name>
```

### Commands

Registry CRUD is a uniform verb set (`list | get | set | rm`) over each collection; `set` reads a JSON/TOML body (file or stdin) and does POST-or-PUT. Ops and reads mirror the API.

```
hrono serve --key-file <path> [--port 8080]           run the server (not a client command)

hrono sources     list | get <name> | set <name> -f f | rm <name>
hrono connections list | get | set | rm               # same shape
hrono models      list | get | set | rm
hrono prompts     list | get | set | rm
hrono users       list | get | set | rm               # admin

hrono trees list | get <name> | set <name> -f f | rm <name>
hrono tree <name> maintain                            # easy button -> prints job id
hrono tree <name> op <op> [--scope '<json>']         # sync|split|embed|cluster|propagate|brief|...
hrono tree <name> export --levels N -o <dir>          # fetch rendered MD, write files to <dir>
hrono tree <name> edit -f f [--dry-run]               # PUT config; --dry-run shows impact + cost

hrono recall <tree> "<question>" [--limit 10]

hrono jobs list [--tree t] [--status s]
hrono job <id>            | watch <id>  (SSE live)  | cancel <id>

hrono admin rotate-key                                # prompts for old + new key
```

`export` is the one command that materializes files: it GETs the rendered MD body and writes the folder/file tree to `<dir>` locally for an agent to traverse. `watch` consumes the job SSE stream.

## Admin dashboard (web UI)

Another HTTP client of the same API — same Bearer token, same reader/writer/admin roles, no separate backend. The place granular control lives: where you go when something looks wrong. Reads existing endpoints; writes go through the manual-adjustment + config endpoints already spec'd.

- **Tree board — expandable node graph, not an outline.** Start at root; expand a node to fan its children onto the canvas (lazy-fetched, local re-layout, collapse prunes) so a million sections never render — you always see a neighborhood. Node size = member count, color = health (red misfit / amber stale / locked pinned). The graph earns its cost via **non-tree edges** an outline can't draw: sibling proximity (which topics nearly touch = merge candidates), a selected misfit's dashed edge to the topic it's actually closest to (that edge is the one-click migrate), and a highlighted root-ward path showing how a change climbed (the judge cascade). ⌘K search jumps to a node and auto-expands the path to it. Optional per-node "local map" for spatial intuition; never the whole tree at once.
- **Health / spot trouble** — per-tree health summary (stale briefs, misfit rate, churn-since-settle, incubator size), job history and failures, the update_log (every judge verdict and propagate/skip decision).
- **Overview is a triage queue** — tiles for act-on numbers (stale briefs, misfit vs baseline, churn bar toward the settle threshold, incubator, failed jobs) over a worklist whose rows deep-link into the board at the offending node.
- **Adjust manually** (admin) — the manual-adjustment endpoints above: rename, override brief, reparent, merge/split/dissolve, move a section, add notes; plus edit any config with the `?dry_run=true` impact preview first, trigger any op at any scope, cancel jobs.
- **Roles gate the UI** — reader sees read-only views; writer runs ops + config edits; admin gets manual tree surgery + users + key rotation. Enforced server-side (the UI only hides what the API already forbids).

## Open / not yet spec'd

- Scheduled/periodic sync (v1 is manual; a cron-style trigger is a later add).
- Export delivery beyond one big MD body (partial responses / streamed download).
