---
id: 081
title: `hrono tree export --levels N -o <dir>` — materialize the folder tree to disk (T32) — MVP CLOSE
priority: high
size: medium
depends_on: [080, 010]
spec_refs: [build-order.md#T32, implementation-notes.md, how-hrono-works.md]
---

## Context
T32, the last MVP ticket. `export` is the one command that MATERIALIZES files:
it GETs the rendered export (#080) and writes the folder/file tree to `<dir>`
locally, so an agent traverses it with the tools it already has — list a
directory, read a brief, descend — no query API in the loop. Completing this is
**M6 = MVP**: ingest -> tree -> recall -> a walkable exported map on disk.

## Description
- `hrono tree export <name> --levels N -o <dir>` (verb-first, per the settled
  `tree`-family grammar): a thin #010 client that GETs `/trees/<name>/export?
  levels=N` and writes the returned tree to `<dir>`.
- Materialize the folder/file tree from #080's payload (the path->content
  manifest, or the split of the one-MD body — whichever #080 settled): create the
  directories and write each file at its relative path under `<dir>`.
- Safe write: refuse to escape `<dir>` (no `..`/absolute paths from the payload —
  sanitize each relative path, like the #026 symlink/traversal lesson); create
  `<dir>` if absent; do not delete unrelated files. Report what was written.
- reader role suffices (it is a GET).

## Acceptance criteria
- [ ] `hrono tree export <name> --levels N -o <dir>` fetches the render and writes
      the folder/file tree under `<dir>`; an agent can `ls`/read/descend it.
- [ ] Every payload path is written under `<dir>`; a malicious/odd path cannot
      escape `<dir>` (path traversal rejected); `<dir>` is created if missing.
- [ ] Leaf files reassemble the byte-identical sections (#079); briefs + Caution
      + mechanical child listings are present and navigable.
- [ ] Clean error on unknown tree / no profile (via the #010 client).
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- The render/endpoint internals (#078-080).
- Streamed download / incremental export (deferred).
- Notes creation (M9) — rendered if present (#079).

## Review log
- 2026-08-25 PO: authored as T32, the MVP-closing ticket. Thin #010 client GETs
  #080's render and materializes the folder tree to disk with path-traversal
  safety (the #026 lesson). Completing this = M6 = the MVP: a source becomes a
  walkable map on disk plus a recall endpoint.
- 2026-08-25 dev: DONE, committed 8ce544b, handoff to qa. `hrono tree export
  <name> -o <dir> [--levels N]`: thin #010 client GETs `/trees/<name>/export?
  levels=N` (#080 manifest) and materializes each {path, content} under <dir>,
  creating dirs. Path-traversal SAFE (the #026 lesson): every target is resolved
  and must stay within <dir> — a `..`/absolute payload path raises UnsafePath ->
  clean exit 1, nothing escapes. Clean errors on unknown tree / no profile via
  the client boundary. reader-role (a GET). Verified: ruff clean; pytest 527
  passed / 1 skip (+3: writes the folder tree with correct content, refuses
  traversal, clean no-profile error); drove the real `hrono tree export --help`.
  **M6 (Export) COMPLETE (078-081) = MVP: source -> tree -> recall + a walkable
  exported map on disk.**
- 2026-08-25 qa: PASS (commit 8ce544b) -> po-review. Tree CLEAN at handoff. The
  MVP-closing CLI is correct on every dimension:
  - Security (the critical piece for a file-writing command): path-traversal is
    the #026 lesson, applied well. `_materialize` resolves each target and requires
    `base` to equal it or be an ancestor (`base in target.parents`); a `../escape.md`
    payload path -> UnsafePath -> clean exit 1, nothing written outside <dir>
    (tested). Absolute payload paths are also caught (`out / "/abs"` resolves to
    the absolute, base not an ancestor -> rejected). symlink escapes are covered by
    `resolve()`.
  - Materialization: thin #010 client GETs #080's manifest and writes each
    {path, content} under <dir> (dirs created), so an agent can ls/read/descend;
    leaf files carry #079's byte-identical section bodies verbatim. Reports the
    file count. Clean errors on unknown tree / no profile via the client boundary.
    Smoke-drove `hrono tree export {name} -o <path> [--levels 4]` (verb-first).
  - ruff clean; full suite 527 passed / 1 skip; atomic Conventional Commit.
  MVP note: 081 faithfully materializes whatever manifest #080 returns, so it is
  correct independent of the multi-root export-completeness gap I filed as #082
  (which the PO has already triaged to a #062 single-root build fix). Full MVP
  export completeness depends on #082 landing, but the CLI/endpoint/render/collapse
  machinery is done and correct. **M6 (Export) = MVP reached: a source becomes a
  walkable map on disk + a recall endpoint** (pending #082 for multi-root corpora).
  (Pre-existing `.gitignore` edit still uncommitted.)
- 2026-08-25 PO review: PASS -> done. Tree clean, #081 is HEAD (8ce544b). Verified
  the security surface MYSELF (critical for a file-writing command): `_materialize`
  resolves `base = out.resolve()` and each `target = (out/path).resolve()`, then
  requires `base == target or base in target.parents` — so `..`, absolute payload
  paths, and symlink escapes (resolve() follows them) are all rejected with a clean
  UnsafePath -> exit 1, nothing written outside <dir>. This is the #026 lesson
  applied correctly. Ran the checks: 12 tree tests pass, ruff clean, full suite
  527 passed / 1 skip. The CLI is a faithful thin #010 client that materialises
  #080's manifest under <dir> (dirs created, byte-identical leaf bodies), verb-
  first grammar, clean unknown-tree/no-profile errors. All acceptance criteria
  met. Closed. **M6 (Export) COMPLETE (078-081) = MVP REACHED: a source ingests ->
  splits -> embeds -> condenses -> clusters -> briefs -> recurses to a root, is
  recallable via `POST /recall` + `hrono recall`, and exports to a walkable folder
  tree on disk via `hrono tree export`.** Caveat honestly stated: full export
  COMPLETENESS on multi-root corpora needs #082 (single-root build guarantee in
  #062), already promoted to todo at high priority; the common single-root corpus
  is fully correct today.
