---
id: 119
title: Pin #098's two unpinned guards, and record the reset symlink boundary
priority: medium
size: small
depends_on: []
spec_refs: [build-order.md#T12]
found_by: qa while verifying 098 on 2026-09-15; filed by PO at its close
---

## Context
#098 added two behaviours that no test covers. qa reported them and PO
confirmed independently: reverting BOTH lines in an isolated worktree leaves the
suite green at **688 passed**.

Neither blocked #098 — neither is an acceptance criterion, neither is reachable
in production, and both were driven and shown correct. They are filed as a
ticket rather than left as a review note because "fold it into the next touch"
is a hope, not a commitment, and an untested fix is the kind that silently
reverts.

## Description

**1. `src/hrono/server/app.py:141` — `cache_root(db_path) if owned else None`.
This is the one that matters.** It is the fix qa asked for in #098's first
round, and it protects the property #098 exists to establish: that no code path
can resolve a cache against the working directory. `cli.py:136` is the only
production `create_app` caller and always passes a resolved path, so the
injected-connection form is test-only — but it is the last route by which a
cwd-relative cache could reach a worker, and it is currently the one piece of
#098 with no regression cover. A fix delivered on review with no test is
exactly what rots.

qa drove the correct behaviour: an app built from an injected connection fails
an ingest job with `no cache root: this job context cannot run ingest ops`, the
server stays up (`/health` 200), and no cwd-relative `.hrono/cache` is created.

**2. `src/hrono/admin/reset.py:99` — `path.is_dir() and not path.is_symlink()`
in `_remove`.** This is what makes the TOCTOU case safe: a symlink-to-directory
is unlinked rather than handed to `shutil.rmtree`, so even a swap between the
refusal check and the delete loop cannot remove anything outside the bound. It
is unreachable in the normal flow because `_refuse_linked_cache` fires first
(and that ordering IS pinned), which is why nothing covers it — so it wants a
direct unit test on `_remove`, not one through `wipe`.

**3. The docstring sentence.** `admin/reset.py`'s module docstring should record
that the symlink guard covers the cache ROOT and not the tree beneath it. PO
drove the boundary: a link at `cache/sources` is unlinked without being
followed — the outside payload survives intact — but the command reports plain
success while orphaned clones remain at the other end. That is a reporting gap,
not a safety gap.

**Do NOT deepen the guard.** A deep scan would have to refuse a cache containing
ANY symlink, and cloned repositories legitimately contain symlinks, so `reset`
would start refusing on ordinary corpora. A destructive command that refuses on
a normal install is a far worse outcome than an orphan in a contrived layout.
Guard the bound, not the tree — settled at #098's close, record it, do not
relitigate it.

## Acceptance criteria
- [ ] A test asserts an injected-connection app fails an ingest job with the
      "no cache root" message and creates no `.hrono` in the working directory;
      it fails if `app.py:141` reverts to an unconditional `cache_root(db_path)`.
- [ ] A direct unit test on `_remove` asserts a symlink-to-directory is unlinked
      and its target left intact; it fails if `and not path.is_symlink()` is
      dropped.
- [ ] `admin/reset.py`'s module docstring states that the symlink guard covers
      the cache root, not the tree beneath it, and why it is not deepened.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- Deepening the symlink guard (see above — settled).
- Any behaviour change at all. All three items pin or document what #098
  already does; if a test fails, the test is wrong.

## Review log
- 2026-09-15 PO: filed at #098's close. qa reported both gaps and did not block;
  PO confirmed both by reverting them together in a worktree (suite still green
  at 688) and accepted the deferral as proportionate — neither is an acceptance
  criterion and neither is production-reachable, and holding the e2e re-run for
  two tests on unreachable routes would cost more than it protects. Filed as a
  ticket so the commitment is real. **The next change to `server/app.py` or
  `admin/reset.py` must carry this ticket**; until then it can be picked up on
  its own at any time — it is small, has no dependencies, and changes no
  behaviour.

## PO triage 2026-09-21 — promoted to `todo`, priority confirmed `medium`

#098's data-location rule is one of the few invariants that has actually bitten
this project (F25: two divergent clone sets for one database, and a diff that
invented a reversed rename). Two of its guards are unpinned. Cheap to close and
expensive to rediscover.

## Review log (dev)
- 2026-09-21 dev: implemented and committed. All four criteria, no behaviour
  change — the only source edit is a docstring.

  **1. The cache-root guard.** A test builds an app from an injected connection
  (the only route by which a cwd-relative cache could reach a worker), asserts
  its ops get NO cache root — `cache_for` raises "no cache root" — and that no
  `.hrono` appears in the working directory. Reverting `app.py:151` to an
  unconditional `cache_root(db_path)` fails it. That is #098's invariant with a
  tooth: F25 was two divergent clone sets for one database and a diff that
  invented a reversed rename.

  **2. The symlink guard**, tested DIRECTLY on `_remove` as the ticket asks,
  not through `wipe` — `_refuse_linked_cache` fires first in the normal flow, so
  a test through the front door would prove nothing about this line. A
  symlink-to-directory is unlinked, the link is gone, and the payload at the
  other end survives intact. Dropping `and not path.is_symlink()` fails it.

  **3. The docstring** records that the guard covers the cache ROOT and not the
  tree beneath it, what that costs (a link deeper down is unlinked without being
  followed, so orphans can remain while the command reports success — a
  reporting gap, not a safety gap), and why it is not deepened: cloned repos
  legitimately contain symlinks, so a deep scan would make `reset` refuse on
  ordinary installs, and a destructive command that refuses on a normal install
  is worse than an orphan in a contrived layout. Settled at #098's close, not
  relitigated.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **888 passed**.
- 2026-09-21 qa: **PASS — to po-review.** All four criteria met, no behaviour
  change, and both guards now bite: reverting `app.py:151` to an unconditional
  `cache_root(db_path)` fails 1, and dropping `and not path.is_symlink()` fails
  1. I also tried making `_remove` REFUSE a symlink rather than unlink it —
  also fails 1, so the test pins the actual behaviour rather than merely "does
  not recurse".

  Testing `_remove` directly rather than through `wipe` is the right call and
  the ticket was right to insist: `_refuse_linked_cache` fires first in the
  normal flow, so a front-door test would have proved nothing about this line.

  The docstring records the boundary, what it costs, and why it is not deepened
  — including the part that matters most, that a deep scan would make `reset`
  refuse on ordinary corpora because cloned repos contain symlinks.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** All four criteria met, no
  behaviour change.

  I filed this because "fold it into the next touch" is a hope, not a
  commitment, and an untested fix is the kind that silently reverts. Both guards
  now bite, and the one that matters — #098's cache-root rule — is the invariant
  whose absence produced F25: two divergent clone sets for one database, and a
  diff that invented a reversed rename.

  The docstring is the part I will point at later. It records not just the
  boundary but the trade behind it: a deep symlink scan would make `reset`
  refuse on ordinary corpora, because cloned repositories legitimately contain
  symlinks, and a destructive command that refuses on a normal install is worse
  than an orphan in a contrived layout. That reasoning was in a review thread
  and is now in the module.
