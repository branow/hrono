---
id: 106
title: API/CLI surface — no trigger for any op but maintain, no config or jobs CLI, PUT cannot create
priority: high
size: big
depends_on: [092, 093]
spec_refs: [implementation-notes.md, build-order.md#T5, build-order.md#T11.4]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F9, F10, F2, F3, F11
---

## Context
```
$ grep -rn "enqueue(" src/
src/hrono/server/trees.py:44:    job_id = enqueue(request.app.state.db, "maintain", {}, tree=name)
src/hrono/jobs/worker.py:23:def enqueue(
```

## Description
**F9 — the incremental lifecycle is unreachable.** `update`, `propagate`,
`monitor`, `repair`, `settle`, `cluster-briefs`, `brief-upper` and every leaf op
are registered in `OPS` and unit-tested, but the only enqueue call site in the
source tree is `maintain`. There is no `POST /jobs`, no
`POST /trees/{name}/update`, and no `hrono jobs` command, so hrono's
differentiating feature cannot be run through any supported interface. Nothing
chains `update -> propagate -> monitor -> repair -> settle` either. The e2e run
had to insert job rows directly and then drive ops in-process
(`.e2e/scripts/drive_op.py`).

**F10 — no config CLI.** Shipped: `serve`, `recall`, `reset`,
`profile {add,list,use,current,rm}`, `admin reset-token`,
`tree {maintain,export}`. The spec's `hrono sources`, `connections`, `models`,
`prompts`, `jobs` do not exist, so registering a source means hand-written curl.

**F2 — `PUT` cannot create.** `CLAUDE.md` and `implementation-notes.md` say
"config is data you PUT", but the engine only creates on `POST`:

```
$ curl -X PUT /sources/tiny -d '{...}'
{"error":{"code":"not-found","message":"sources not found: tiny"}}   404
```

**F3 — wrong port in the bootstrap hint.** Served with `--port 8299`, the
first-run message prints
`hrono profile add local --server http://127.0.0.1:8080 --token <token>`;
`cli.py:_bootstrap_message` uses a literal instead of the given host/port.

**F11 — two error envelopes.** Body validation returns
`{"error":{"code":"validation-error",...}}`, query validation returns FastAPI's
raw `{"detail":[...]}` (e.g. `GET /trees/default/export?levels=abc`).

## Decision (2026-09-12, dev — technical call, no PO input needed)

Technical half, decided: `PUT /{collection}/{name}` creates or replaces
idempotently; the bootstrap hint is built from the host/port the server was
given; query-param validation errors go through the app error envelope.

## OPEN — needs a product call (see the PO note of 2026-09-12)

The shape of the operator-facing surface — which ops are triggerable, whether
there is one "bring my knowledge base up to date" command, and what it runs —
is a product call. See the PO note of 2026-09-12, question D.

## Acceptance criteria
- [ ] Every registered op is triggerable over HTTP (a generic `POST /jobs` with
      `{op, scope}` behind the writer role, or per-op endpoints) and from the CLI.
- [ ] An incremental chain (`update -> propagate -> monitor -> repair -> settle`)
      is runnable as one command/endpoint.
- [ ] `hrono sources|connections|models|prompts|jobs` exist with list/get/set/rm.
- [ ] `PUT /{collection}/{name}` creates or replaces idempotently.
- [ ] The bootstrap hint prints the host/port the server was started with.
- [ ] Query-param validation errors use the app error envelope.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log (PO)
- 2026-09-21 PO: **SPLIT and closed.** Note D was decided with the product owner
  today: ONE operator verb, individual stages as an admin-only debug door, hrono
  never acting on its own, and one surface serving CLI, API and the future
  dashboard alike. The full ruling is in `docs/evaluations/2026-09-manual-qa/po-decisions.md` section D.

  This ticket was `big` and covered five distinct findings; holding them in one
  card would have meant one enormous review. Split into three, each landing and
  being reviewed on its own:

  - **#137** — the `sync` op: the chain, in order, composing existing ops. The
    product decision made real.
  - **#138** — `hrono tree sync <name>` plus the surface fixes that belong with
    it: the config CLI (F10), `PUT` creating (F2), the bootstrap hint's real
    port (F3), and one error envelope (F11). All four were already settled as
    technical calls on 2026-09-12 and are the same surface, so they ship
    together.
  - **#139** — `POST /jobs {op, scope}`, admin-only, no CLI command: the door
    for a stuck tree.

  Nothing is dropped; F9's acceptance criterion ("every registered op is
  triggerable ... and from the CLI") is the one thing deliberately NOT carried
  forward, because the ruling says the CLI half of it is wrong. Stages are
  reachable over HTTP by an admin (#139) and not from the CLI, on purpose.

  Closing this card rather than leaving it as a parent: the three children carry
  the whole of it and a parent with no remaining work is just a place for
  confusion to accumulate.
