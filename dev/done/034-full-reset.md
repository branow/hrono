---
id: 034
title: `hrono reset` — full DB wipe behind explicit confirmation (recovery)
priority: medium
size: medium
depends_on: [002]
spec_refs: [build-order.md#T4, implementation-notes.md, admin-recovery-and-reset]
---

## Context
Promoted from the stakeholder backlog request `admin-recovery-and-reset`. Today
the only guaranteed way back in after losing the admin token is the undocumented
trick of deleting `.hrono/hrono.db` (+ `-wal`/`-shm`) so the next `serve`
re-bootstraps. This ticket makes that a first-class, discoverable, SAFE command:
a **nuclear** reset that wipes the database behind an explicit confirmation, after
which `serve` bootstraps a fresh admin. Pairs with #033 (targeted, no-data-loss
recovery). Load `engineering:security` for the destructive-action guardrails.

## Description
Add `hrono reset` to the Typer CLI. It:
- Deletes the local hrono database and its SQLite sidecars
  (`.hrono/hrono.db`, `-wal`, `-shm`) so the next `serve` re-applies migrations
  onto a fresh file and re-bootstraps a new admin token (#007).
- **Requires explicit confirmation** and NEVER runs silently: an interactive
  "type the DB path / 'yes' to confirm" prompt, bypassable only with an explicit
  `--force` flag for non-interactive use. Clearly state that this DESTROYS ALL
  DATA (users, registries with their encrypted secrets, jobs, ingested content).
- Is a local recovery command: no Bearer token, no master key required (it is
  deleting the file). Trust boundary = local filesystem access.
- **Safety**: only ever removes the resolved hrono DB path + its known sidecars;
  refuse to run if the target does not look like a hrono DB (never rm an
  arbitrary path). If no DB exists, say so and exit 0 (nothing to do). Report
  exactly what was removed.
- On a running server the DB file is owned by the single writer; document that
  `reset` is meant to run while the server is stopped (and behave sanely / warn
  if a lock is held rather than corrupting a live file).

Errors render via the #027 `AppError` + CLI helper (clean one-line message,
non-zero exit, no traceback). This replaces the "delete the file" folklore with a
supported command whose help tells a locked-out operator how to recover.

## Acceptance criteria
- [ ] `hrono reset` with confirmation (prompt answered, or `--force`) deletes
      `.hrono/hrono.db` + `-wal` + `-shm`; a subsequent `serve` re-bootstraps and
      prints a fresh admin token.
- [ ] Without confirmation (prompt declined, no `--force`) it makes NO changes
      and exits non-zero with a clear "aborted" message; it never wipes silently.
- [ ] It refuses to delete a path that is not the resolved hrono DB (no arbitrary
      rm); with no DB present it reports "nothing to reset" and exits 0.
- [ ] It requires no Bearer token and no master key; it reports exactly which
      files were removed.
- [ ] Help text documents this as the discoverable recovery-from-lockout command
      and warns it destroys all data.
- [ ] Regression-grade tests (temp HRONO dir): confirmed wipe removes the files
      and lets a fresh open re-bootstrap; declined/`--force`-absent leaves the DB
      intact; non-hrono path refused; missing-DB no-op; only the known files are
      touched.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Targeted token reissue without data loss (#033).
- Partial/selective reset (dropping one collection) — full wipe only.
- Backups/export before reset (a user wanting to keep data uses #033 instead).

## Review log
- 2026-08-16 PO: triaged from the stakeholder `admin-recovery-and-reset` request
  (nuclear half; targeted is #033). Medium priority - replaces undocumented
  file-deletion folklore with a safe, confirmed, discoverable command. Guardrails
  (confirmation, refuse-non-hrono-path, never-silent) are acceptance criteria,
  not nice-to-haves, given it is destructive.

## dev — 2026-08-16

Added top-level `hrono reset` (cli.py) + `src/hrono/admin/reset.py`. The module
is pure/testable: `wipe(db_path)` removes the DB and its `-wal`/`-shm` sidecars
and returns the removed files; `targets()` lists what exists; a hard guard
refuses any path whose name != `hrono.db` or whose parent != `.hrono`
(`NotHronoDatabase`, an AppError), so it can never rm an arbitrary path. The CLI
owns confirmation: it lists the doomed files, requires `typer.confirm` (default
No) unless `--force`, and on decline prints "Aborted; nothing was changed" and
exits 1 — never silent. Missing DB -> "nothing to reset", exit 0. Reports exactly
which files were removed and points at `serve` to re-bootstrap.

Security (engineering:security): destructive action gated behind explicit
confirmation + refuse-non-hrono-path + never-silent, all as tested guarantees.
No Bearer token, no master key (it deletes the file); trust boundary = local
filesystem access, stated in help. On POSIX, unlinking the DB while a server
holds it removes the dir entry without corrupting the live inode; help documents
"run while the server is stopped" rather than adding OS-specific lock detection.

Verified on the real binary: declined prompt aborts (exit 1, DB intact);
`--force` removes `.hrono/hrono.db` (exit 0) and a re-run reports "nothing to
reset" (exit 0); a non-hrono path is refused with the file left intact. Tests
(temp HRONO dir): --force wipe removes all three files and a fresh open +
bootstrap re-mints admin; confirmed-prompt wipe; declined leaves DB intact +
exit!=0; missing-DB no-op exit 0; a bystander file in `.hrono` survives;
non-hrono path refused; help documents recovery + data loss.

Namespace: `hrono reset` is top-level per the ticket (pairs with the targeted
`hrono admin reset-token` from #033). Gate clean: ruff format/check, pytest 311
passed. Commit b3c1964.

## qa — 2026-08-16

PASS -> po-review. Verified all dimensions (engineering:security lens on the
destructive-action guardrails). Gated 034 IN ISOLATION (the working tree carried
unrelated #014/#017 WIP - `server/auth.py`, `test_users.py`, `ingest/sync.py`,
`registry/git_auth.py`, `registry/git_validation.py`; 034 touches none of them):
stashed the WIP, ran the gate clean on the 034 commit (ruff format/check, pytest
311 passed), then restored the WIP. Drove the real binary through every
guardrail: a missing DB prints "nothing to reset" and exits 0; a DECLINED prompt
lists the doomed files, prints "Aborted; nothing was changed", exits 1, and
leaves the DB intact (never silent); `--force` removes exactly
`.hrono/hrono.db` + `-wal` + `-shm` (exit 0, reports each) while a bystander
`.hrono/keep.txt` SURVIVES; a subsequent `serve` re-bootstraps a fresh admin
token. The refuse-non-hrono-path guard is the critical safety and it holds:
`wipe()` on `important.db` and on a `hrono.db` outside a `.hrono` dir both raise
`NotHronoDatabase` (an AppError, code `not-hrono-database`) with the victim files
intact - it can never rm an arbitrary path (guard is name==hrono.db AND
parent==.hrono). No Bearer token and no master key required; help documents the
lockout recovery and that it DESTROYS ALL DATA. Errors render via #027's
`cli_message` (clean line, exit 1, no traceback). Tests are regression-grade
(force-wipe+rebootstrap, confirmed-prompt, declined-intact-exit!=0, missing-DB
no-op, only-known-files-removed, refuse-non-hrono-path, no-token/key, help). Code
review clean: pure `wipe`/`targets`/`sidecars` in a testable module, CLI owns
confirmation, typed, docstrings only, no emojis; scope correct (full wipe, not
targeted #033 or selective). Commit b3c1964 is a proper atomic Conventional
Commit. Process note (recurring): 034 was reviewed against a tree dirty with two
OTHER tickets' uncommitted WIP - reiterating the standing ask to keep the tree
clean between tickets; 034's own commit is clean and independently verified.
- 2026-08-16 PO: PASS -> done. Drove every destructive guardrail on the real
  binary (tree clean at HEAD): missing DB -> "nothing to reset" + exit 0; a
  DECLINED prompt lists the doomed files with a "DESTROYS ALL DATA" warning
  (default No), prints "Aborted; nothing was changed", exits 1, and leaves the DB
  intact (never silent); `--force` removes exactly .hrono/hrono.db + -wal + -shm
  (reports each, exit 0) while a bystander .hrono/keep.txt SURVIVES; a subsequent
  serve re-bootstraps a fresh admin. The critical refuse-non-hrono-path guard
  holds: `wipe()` on `important.db` AND on a `hrono.db` outside a `.hrono` dir
  both raise NotHronoDatabase (code not-hrono-database) with the victim intact -
  it can never rm an arbitrary path (name==hrono.db AND parent==.hrono). No
  Bearer/no master key; help documents the lockout recovery + data loss; errors
  via #027 cli_message (clean, exit 1, no traceback). Ran the gate: ruff format
  (114 clean), ruff check clean, pytest 317 passed. Completes the admin-recovery
  stakeholder request (#033 targeted + #034 nuclear). Closed at b3c1964.
