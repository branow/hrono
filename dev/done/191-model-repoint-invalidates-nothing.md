---
id: 191
title: repointing a model at another upstream model invalidates nothing
priority: high
size: medium
depends_on: [064, 190]
spec_refs: [implementation-notes.md]
---

## Context
Found while building #190's preview. `briefs._is_fresh` compares the brief's
recorded `model_name`, which is the REGISTRY row's name. So:

    PUT /models/sonnet  { ..., "model": "claude-opus-5" }

changes which upstream model every future brief is written by, and marks
nothing stale. Every existing brief keeps reading as fresh, written by
"sonnet", and the tree silently holds two generations of words from two
different models under one name.

The spec says the opposite at `implementation-notes.md:52`: "a model edit
invalidates its role's outputs". #190's preview reports the truth rather than
the spec's wish, and says so in the operator's face — this ticket makes the
truth match the spec instead.

The same hole exists for a prompt's `role` being repointed, and for the
`params` a model is called with. All three are "the provenance records a NAME
and the name did not change".

## Description
- Record a **model fingerprint** in a brief's provenance beside `prompt_hash`:
  a hash of the resolved model config that affects output — the upstream
  `model` string and `params` — NOT the registry name, and not the connection
  (a credential rotation changes no words, #190).
- `_is_fresh` compares it, so the next `brief` run selects what a repoint
  changed. One rule, one place, as the prompt hash already is.
- **A brief written before this existed has no fingerprint, and that is not
  staleness.** NULL means "unknown provenance", and invalidating every brief in
  every install on upgrade would be a re-brief bill nobody asked for. It
  becomes accurate as briefs are rewritten.
- #190's preview stops being a disclaimer and starts being a count: the model
  case reports the nodes a repoint would rewrite.

## Acceptance criteria
- [x] Changing a model's upstream `model` string marks its briefs stale, and
      the next `brief` run rewrites exactly those.
- [x] Changing its `params` does too.
- [x] Changing the CONNECTION it uses does not — no words change.
- [x] Renaming nothing and re-PUTting the same config changes nothing.
- [x] A brief with a NULL fingerprint stays fresh; rewriting it fills it in.
- [x] `_is_fresh` is still the only place freshness is decided.
- [x] #190's model preview reports the real count and drops the disclaimer.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-27 po: authored out of #190. Ranked HIGH: it is a silent
  wrong-answer, and the kind an operator only finds by noticing two voices in
  one tree.
- 2026-09-27 dev: `0034_brief_model_fingerprint.sql` plus
  `resolve.model_fingerprint`, written by both brief ops and read by
  `briefs._is_fresh`.
  - The fingerprint hashes what decides the WORDS — the upstream `model`
    string and `params` — and nothing else. Not the registry name (that is the
    hole) and not the connection (a credential rotation changes no words).
  - `_is_fresh` is still the only place freshness is decided; the fingerprint
    is a fourth term in it, not a second rule beside it.
  - NULL is unknown provenance, not staleness. Every brief written before this
    column carries one, and invalidating them on upgrade would bill every
    install for a corpus that has not changed.
  - #190's model preview is a count now, not a disclaimer. It asks
    `stale_or_missing` under the prompt hash those briefs actually carry — ask
    it under a different one and the prompt mismatch alone makes everything
    stale under both fingerprints and the difference comes back empty.
  - Mutations, all killed: freshness ignoring the fingerprint; NULL treated as
    stale; the connection folded in; the NAME hashed instead of the model;
    `params` dropped; the op not writing it.
  - UPGRADE DRIVE, on a real old database: built one in a `git worktree` at the
    previous commit (no `model_fingerprint` column), then opened it with this
    code. The column appears, the existing brief survives with NULL, it stays
    FRESH under a different fingerprint, and it still goes stale when its
    prompt really changes.
  - Gate: 1387 passed, 2 skipped.
- 2026-09-27 qa: verified. The test that carries the most weight is
  `test_briefs_still_agree_with_the_preview`: the number #190 shows and the
  work the `brief` op then does are asserted to be the same, so the preview
  cannot drift from the run it is previewing.
- 2026-09-27 po: accepted. Found by building the preview, which is the value of
  a feature that has to state what the system really does: #190 could not
  describe this one honestly without exposing it.
