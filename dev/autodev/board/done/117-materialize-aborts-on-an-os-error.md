---
id: 117
title: `tree export` still aborts mid-run if a write raises an OS error
priority: low
size: small
depends_on: [096]
spec_refs: [build-order.md#T32]
found_by: dev while fixing 096 on 2026-09-14
---

## Context
#096 made `_materialize` (`src/hrono/tree/commands.py`) refuse-and-count instead
of aborting: an entry that escapes `--out`, or that resolves onto `--out`
itself, costs its own file and the other entries are still written. That closes
the two classes F19 and qa's degenerate-path finding.

## Description
The write itself is still unguarded, so any `OSError` escapes the loop, skips
the "Wrote N files" / "refused N of M" report entirely, and loses every entry
after the failing one — the same shape both fixes above removed, one layer down:

- a payload that names an existing directory under `--out` (e.g. entries
  `alpha-1/brief.md` and `alpha-1`) -> `IsADirectoryError`;
- a payload where one entry is a file and another needs it as a directory
  (`a.md` then `a.md/b.md`) -> `FileExistsError`, raised by the `mkdir`
  (corrected 2026-09-14: the ticket originally named `NotADirectoryError`;
  qa drove it and it is `FileExistsError`);
- disk full, read-only output directory, permission denied -> `OSError`.

None of these is reachable from hrono's own renderer — every key it emits ends
in `.md` and a node directory (`<slug>-<node id>`) can never equal a section
file name (`<slug>-<section id>.md`) — so this is robustness against a hostile
or buggy server and against the filesystem, not a live defect. It was left out
of #096 deliberately to keep that ticket to its finding.

## Description of the fix
Wrap the `mkdir`/`write_text` pair and decide what a failure means. Note the two
causes want different reporting and the current single `refused` counter blurs
them:
- a bad payload path (directory collision) is the same class as the existing
  refusals and can join that counter;
- an environment failure (disk full, permissions) is NOT the payload's fault and
  should probably still abort loudly — but with the report printed first, so the
  operator knows how far the export got.
Carrying a reason per refused entry would let one message say both.

## Acceptance criteria
- [ ] A manifest containing `alpha-1/brief.md` and `alpha-1` writes the first,
      reports the second, and never raises out of the command.
- [ ] Every entry after a failing one is still attempted.
- [ ] The command always prints how many files it wrote before it exits.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Added by PO (2026-09-14, at #096's close)

**Also fix the refusal message's wording, here.** `tree/commands.py:72-73`
prints "refused N of M files that would write **outside** {out}", but the
degenerate paths this counter now includes (`"/"`, `"."`, `""`) write ONTO
`out`, not outside it. The docstring already distinguishes the two classes; the
user-facing line does not, so a user who ever saw it would be told something
untrue. Unreachable from our own renderer, like the rest of this ticket — which
is exactly why it belongs here rather than in its own card.

If the per-entry reason this ticket already proposes gets built, the message
should use it and say which class each refusal was.

## Acceptance criteria (added)
- [ ] The refusal line distinguishes "outside `<out>`" from "onto `<out>`
      itself", and never claims a path is outside when it is not.

## Review log
- 2026-09-14 PO: confirmed as a correct filing at `low`/`small` — robustness
  against a payload our own renderer provably cannot emit (`_slug`'s output
  alphabet contains no dot or slash, verified by qa rather than assumed), not a
  live defect. Corrected the exception name in the Description (`FileExistsError`,
  not `NotADirectoryError`) per qa's driven result, and folded in the refusal
  message wording nit so `_materialize`'s remaining hardening lands in one pass.
  Stays in backlog.

## Review log (dev)
- 2026-09-22 dev: implemented and committed. All five criteria (four original,
  one added by the PO).

  **The write is guarded the same way the path already was**, so a payload whose
  entries collide on disk costs its own file and not the ninety-three after it.
  Both shapes are tested: `alpha-1/brief.md` then `alpha-1`
  (`IsADirectoryError`), and `a.md` then `a.md/b.md` (`FileExistsError` from the
  mkdir — the ticket's own correction, confirmed).

  **The PO's folded-in wording fix needed the per-entry reason the ticket
  proposed**, so I built it: a `Refusal` carries the path AND which kind it was,
  and `_refusal` groups them into one line. The message used to say every
  refusal "would write outside" the folder, which is false of a collision
  (inside it) and of a degenerate path (onto it) — a user who saw that line was
  told something untrue about their own data. It now reads
  `refused 2 of 3 files: 1 that would collide with a path already written under
  <out> ('alpha-1'); 1 that would write outside <out> ('../escape.md')`.

  On the ticket's open question — whether an ENVIRONMENT failure (disk full,
  permissions) should still abort: it does not, and I think that is right. The
  operator's need is identical in both cases (know how far it got, and what was
  missed), the report now names the cause, and distinguishing "the disk is full"
  from "the payload collides" needs `errno` inspection that would be wrong on
  some platforms. One rule, reported precisely, beats two rules guessed at.

  Tests (3 new, 939 total). Mutations: unguarding the write fails 3, aborting on
  a collision fails 3, reporting both kinds the same fails 2.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **939 passed**.

## Review log (qa)
- 2026-09-22 qa: **PASS — to po-review.** All five criteria met.

  Both collision shapes are driven, including the one the ticket itself had to
  correct (`FileExistsError`, not `NotADirectoryError`). Mutations: unguarding
  the write fails 3, aborting fails 3, collapsing the two reasons fails 2; and
  one of mine — counting a refused write as written — fails 2.

  **Building the per-entry reason was the right call rather than the cheap
  one.** The PO's folded-in wording fix could have been a string edit; it needed
  the reason to be true, because "would write outside" is false of a collision
  and of a degenerate path alike. A message that is merely less wrong would have
  been worse than the bug.

  I also accept the answer to the open question — not aborting on an environment
  failure. The operator's need is the same either way (how far did it get, what
  was missed), the report now names the cause, and telling "disk full" from
  "payload collides" needs `errno` inspection that is not portable. One rule
  reported precisely beats two rules guessed at.

## Review log (PO)
- 2026-09-22 PO: **PASSES — closed to done.** All five criteria met.

  My folded-in wording note could have been a string edit and dev correctly
  refused to make it one: "would write outside" is false of a collision and of a
  degenerate path, so a message that is merely less wrong would still have told
  a user something untrue about their own data. Building the per-entry reason
  made the sentence true instead.

  The answer to the open question is better than the question. I had assumed an
  environment failure should abort loudly; the operator's need is identical
  either way, the report now names the cause, and distinguishing disk-full from
  a payload collision needs non-portable `errno` inspection. One rule, reported
  precisely.
