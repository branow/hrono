---
id: 038
title: Optional-extras group for the in-process embedding backend
priority: medium
size: small
depends_on: [035]
spec_refs: [pyproject.toml, build-order.md#T16]
---

## Context
Spun off from #035 PO review. The `embed` op loads `sentence-transformers`
lazily and treats it as optional (missing backend -> clean `EmbedError`), which
correctly keeps heavyweight `torch` out of the default install (matching the #019
model-validation precedent). But there is currently NO supported way to INSTALL
the embedding backend - it is undeclared, so a user must manually
`pip install sentence-transformers`. In-process embedding is required for
clustering (M3) and recall (M5), so there must be a documented, one-command way
to enable it.

## Description
Add an optional-dependencies extras group so in-process embedding is installable
without bloating the default install:
- `[project.optional-dependencies]` `embed = ["sentence-transformers>=...", ...]`
  (pin a range; include whatever the in-process runner imports - the transitive
  `torch` comes with it). Confirm the exact package set the #035 runner needs.
- Document it: installing hrono with in-process embedding is
  `uv pip install "hrono[embed]"` (or the uv equivalent), and without it the
  `embed` op fails with the existing clear "backend is not installed" message.
- Keep the default install lean (no torch); the extras are opt-in.
- If a remote-embedding path (HTTP connection) is added later, it needs no extra.

## Acceptance criteria
- [ ] `pyproject.toml` declares an `embed` optional-extras group with
      `sentence-transformers` (pinned range); the default install does NOT pull
      it (or torch) in.
- [ ] Installing the `embed` extra makes the in-process `embed` op work
      end to end (with a real or a documented-in-test-as-skipped backend); without
      it, the op still fails with the clean "in-process embedding backend is not
      installed" message (no traceback) - unchanged from #035.
- [ ] The install command is documented (README/help or the relevant doc) so an
      operator knows how to enable in-process embedding.
- [ ] Lockfile updated consistently; `ruff format`, `ruff check --fix`, `pytest`
      all clean; work committed.

## Out of scope
- Changing the #035 lazy-import / clean-failure behavior (kept as-is).
- Bundling torch into the default install.
- Remote-embedding-model support.

## Review log
- 2026-08-16 PO: authored from #035 review ratification. Medium/small - the
  lazy-optional backend is correct, but a supported install path must exist
  before the embedding path is exercised e2e (M3 cluster / M5 recall). Confirm
  the exact package set the runner imports.

## dev — 2026-08-16

Declared the opt-in embedding backend as a `pyproject` optional-extras group:
`[project.optional-dependencies] embed = ["sentence-transformers>=3.0,<6"]`
(torch comes transitively). The #035 runner imports only `sentence_transformers`,
so that is the whole set. Ran `uv lock` to resolve the extra into uv.lock
(sentence-transformers/torch/transformers/... now in the lock's optional group);
the default install still pulls neither — verified `torch` is absent from the
default env after sync.

Documented in README ("In-process embedding" section): enable with
`uv pip install "hrono[embed]"`; without it the default install has no torch and
`embed` fails with the existing clean "in-process embedding backend is not
installed" message. Inline pyproject comment says the same.

#035 lazy-import / clean-failure behavior unchanged. Tests: the existing
missing-backend test still covers the no-extra path (clean EmbedError, no
traceback); added a skipif test that imports the backend when the extra is
installed (skipped on the lean default install — the documented-as-skipped path).
Gate clean: ruff, pytest 368 passed, 1 skipped. Commit 7c97921.

## qa — 2026-08-16 — PASS -> po-review

Re-ran the gate MYSELF: `ruff format --check` + `ruff check` clean, `pytest` 368
passed, 1 skipped (the backend-present skipif). Verified the packaging directly:

- `pyproject.toml` declares `[project.optional-dependencies] embed =
  ["sentence-transformers>=3.0,<6"]`; the default `dependencies` list has neither
  sentence-transformers nor torch. `uv lock --check` passes (lock consistent with
  pyproject); torch + sentence-transformers resolve only in the lock's optional
  group.
- Default env is genuinely lean: `find_spec('sentence_transformers')` and
  `find_spec('torch')` are both None, so `encoder_for(...)` on the default install
  fails with the exact clean "in-process embedding backend is not installed"
  EmbedError (no traceback) — unchanged from #035.
- README "In-process embedding" section documents `uv pip install "hrono[embed]"`
  and the clean-failure fallback; inline pyproject comment matches.
- The skipif test imports the backend only when the extra is present and does NOT
  load weights (stays offline), skipped on the lean install — the
  documented-as-skipped e2e path.

Range-pin in pyproject + exact pin in uv.lock is the standard uv pattern and
matches the rest of this repo's deps (security skill's "pin exact" is satisfied by
the committed lock). `chore:` is the right commit type for a packaging change; one
atomic commit (7c97921). All ACs met; closes the #035 install-path follow-up.
- 2026-08-17 PO: PASS -> done. Verified the packaging directly: pyproject
  `[project.optional-dependencies] embed = ["sentence-transformers>=3.0,<6"]`
  (torch transitive); the default `dependencies` list has NEITHER torch nor
  sentence-transformers (grep clean); README "In-process embedding" documents
  `uv pip install "hrono[embed]"` + the clean-failure fallback; inline pyproject
  comment matches. qa confirmed the default env is genuinely lean (find_spec None
  for both -> the #035 clean "backend is not installed" EmbedError, unchanged),
  uv lock --check consistent, and the skipif backend test skips on the lean
  install. Gate 368 passed / 1 skipped (covered at HEAD). Range-pin + committed
  lock is the standard uv pattern. Closes the #035 install-path follow-up; the
  lazy-optional backend now has a supported install path before M3 cluster / M5
  recall exercise it e2e. Closed at 7c97921.
