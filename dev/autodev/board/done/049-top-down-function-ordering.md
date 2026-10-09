---
id: 049
title: order modules top-down (high-level entry points first, helpers below)
priority: low
size: small
depends_on: []
spec_refs: []
---

## Context
The coding-principles skill wants top-down / "newspaper" ordering: high-level
entry points first, lower-level helpers below. Some modules invert this — e.g.
`context/commands.py` defines the `_store` and `_guard` helpers at the TOP, above
the command functions that are the module's real subject. This is NOT a Python
requirement: names resolve at call time, so a helper defined lower can be called
by a function defined higher (only the `@app.command` decorators run at import,
and they do not call the helpers). The top placement is a define-before-use habit
from other languages, not a necessity.

## Description
An opportunistic hygiene pass (per touched file, NOT a big-bang PR): move
low-level helpers BELOW the high-level functions they serve so a reader meets the
module's purpose first and drills down. Canonical example: `context/commands.py`
(commands first, then `_store` / `_guard`). Behavior-preserving reordering only.

## Acceptance criteria
- [ ] In touched files, module-level helpers sit below the high-level functions
      that use them; public entry points read first.
- [ ] No behavior change; pure reordering (diff is moves only).
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean.

## Out of scope
- Any logic change or extraction (that is other tickets, e.g. #048).
- A single sweeping reorder of every module at once; do it as files are touched.

## Review log
- 2026-08-22 stakeholder + PO: noted during review of #011 that `_guard`/`_store`
  sit above the commands, inverting the skill's top-down ordering. Confirmed it
  is style, not a Python constraint. Low-pri opportunistic cleanup.
- 2026-09-27 po: CLOSED as a CONVENTION rather than a ticket. Both halves of
  this ticket say the same thing — "opportunistic, per touched file, NOT a
  big-bang PR" — which is the definition of a standing rule, not of work with
  an end. It now lives in `CONTRIBUTING.md` under "Form, applied as files are
  touched" (#171 created that file for exactly this), where it applies to every
  ticket automatically instead of waiting in a backlog nobody can finish.
