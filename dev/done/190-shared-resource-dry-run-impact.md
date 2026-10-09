---
id: 190
title: dry-run a shared-resource edit — tree-keyed impact (T58, impact half)
priority: medium
size: big
depends_on: [054, 064, 179]
spec_refs: [build-order.md#T58, implementation-notes.md]
---

## Context
#178 parked T58 in two halves: impact was computable, cost was not, because
nothing recorded tokens. #179 shipped the per-job token record, so the cost
half is now possible too — but it is an ESTIMATE from measured history and a
different question, so it stays its own ticket. This is the impact half.

Spec: `PUT|PATCH /<collection>/<name>?dry_run=true` applies nothing and returns
tree-keyed impact. Plus the rule at `implementation-notes.md:53`: "auth-only
edit = no staleness (same bytes); url/scope edit = content changes, referencing
trees go stale on next sync".

## The rule this ticket must not break
**Report what the system actually does, never what the spec wishes it did.**
Freshness is decided in ONE place — `briefs._is_fresh`, through
`stale_or_missing` — and it compares the brief's recorded `prompt_hash` and
`model_name`. So:

- A **prompt** edit changes the template hash, and every brief written under
  the old one is selected by the next `brief` run. That is real staleness, and
  the dry-run computes it by asking `stale_or_missing` with the PROPOSED hash
  and subtracting what is already stale — the same function, not a copy of its
  rule.
- A **model** edit that changes the row's upstream `model` string changes
  NOTHING by that rule: provenance records the registry NAME. The preview must
  say so rather than claim a rebuild. (That gap is real, and is #191.)
- A **condense** prompt edit does not mark any brief stale either, for the same
  reason: the brief's provenance does not record what produced its inputs.
- A **source** edit is auth-only or scope-changing. Auth-only: nothing. Scope:
  the referencing trees (#054) re-sync, and how many SECTIONS change is not
  knowable without doing it — so `sections` is null with a reason, never a
  number nobody measured.

## Description
- `?dry_run=true` on PUT for every collection, in the ENGINE, so it is one
  implementation and every collection has it.
- It validates the body (a dry-run of an invalid edit is a validation error,
  not an impact report) and runs the descriptor's hooks, then applies nothing.
- `{"affected_trees": [{"tree": ..., "stale": {"sections": n|null, "nodes": n,
  "levels": [...]}, "ops": [...], "reason": "..."}]}` — `reason` is prose for
  the operator, and is where "nothing goes stale, and here is why" lives.
- An edit that changes nothing observable reports no affected trees at all.

## Acceptance criteria
- [x] `?dry_run=true` writes nothing — asserted by reading the row back.
- [x] A prompt edit reports the nodes that would need a re-brief, counted
      through `stale_or_missing` and not through a second rule.
- [x] Nodes ALREADY stale are not counted as this edit's blast radius.
- [x] A pinned brief is not counted — the pin holds whatever the prompt says.
- [x] An auth-only source edit reports no staleness; a url edit reports the
      referencing trees with `sections: null` and a reason.
- [x] A source edit reports only the trees whose scope includes it (#054).
- [x] A model edit that changes only the upstream model string says plainly
      that nothing is marked stale by it.
- [x] An invalid body is a validation error in dry-run too.
- [x] A dry-run needs the collection's own write role, not reader.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-27 po: authored as the impact half of #178, which #179 unblocked.
- 2026-09-27 dev: `registry/impact.py` plus `?dry_run=true` on PUT in the
  ENGINE, so every collection has the safety rather than the ones someone
  remembered.
  - `summarize.brief._hash` moved to `resolve.template_hash` and is now shared.
    The preview has to hash the way the op that later reads the provenance
    hashes; a second `sha256` call is not the same function, and with a
    different one every node reads as stale under BOTH hashes and the preview
    quietly reports zero.
  - The blast radius is `stale_or_missing(proposed) - stale_or_missing(current)`
    — the same selection the `brief` op makes, so a pinned brief (#154) and an
    already-stale one fall out of the answer for free rather than through a
    second rule that could drift.
  - Three cases report NOTHING stale, and say why: an auth-only source edit
    (same bytes), a condense/judge prompt edit (a brief's provenance does not
    record what produced its inputs), and repointing a model at another
    upstream model (provenance records the registry NAME). The last is a real
    gap, not a design — see #191.
  - `sections` is null for a source url change, with the reason in the row.
    How many sections a new url yields is not knowable without doing the sync.
  - Mutations, all killed: dry_run writing; already-stale counted; auth treated
    as content; tree scope ignored; `sections` invented as 0; the model preview
    claiming a rebuild; validation skipped; a second hash function; the
    role/level mapping inverted, and then dropped (this last one SURVIVED at
    first — see qa).
  - The source tests run against REAL local git repositories, because the
    write-time reachability check is real and "an auth-only edit changes
    nothing" is a claim about a source the engine accepted.
  - Driven live on :8796 against the SEEDED brief prompt over two trees:
    3 nodes each at level 0, ops ["brief"], and the stored template unchanged.
  - Gate: 1374 passed, 2 skipped.
- 2026-09-27 qa: verified, with one finding raised and fixed.
  - FINDING (fixed): dropping the role/level filter entirely left every test
    green — the "property held by something else" shape, because `brief` and
    `brief-upper` happened to hold different template text in the fixture, so
    the upper level fell out of the diff anyway. Nothing stops an install from
    wording them alike. A test that gives them the SAME text now pins the rule:
    the roles are told apart by ROLE, not by their words.
  - Added: an upper-level prompt edit reports level 1 and `brief-upper`; a leaf
    edit leaves the upper level alone; a tree whose briefs are missing gains
    nothing from an edit (they are rewritten either way).
  - Noted, not fixed: the spec says `PUT|PATCH` and this engine has no PATCH
    route at all — not a gap this ticket introduced, and a partial-update verb
    is its own question. The dashboard has no dry-run button either; that was
    T55's other half and stays with it.
- 2026-09-27 po: accepted. The three "nothing goes stale, and here is why" rows
  are the part of this ticket that will matter: a preview whose zero is
  indistinguishable from a bug is not a safety. The model-name gap it exposes
  is now #191, and the cost half of T58 is #192.
