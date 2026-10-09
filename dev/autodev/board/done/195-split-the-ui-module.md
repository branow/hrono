---
id: 195
title: split the dashboard module — 850 lines and 21 routes in one file
priority: low
size: small
depends_on: [180, 189]
spec_refs: []
---

## Context
`server/ui.py` grew from #180 to #189 and is now 850 lines carrying 21 routes,
the auth shim, the form reader, five page renderers and nine write routes.
CLAUDE.md forbids god objects and file sprawl, and this is one file doing the
work of a package. It is also entirely MINE — it grew a ticket at a time, which
is how every such file happens.

The import surface is tiny: `server/app.py` imports `LoginRequired` and
`router`, and nothing else in the tree imports it. So the split costs two lines
outside the package.

## Description
A package, one module per subject, sharing one router:
- `ui/__init__.py` — the router, and what every page needs: `_fields`,
  `LoginRequired`, the role dependencies, the templates, `_trees`.
- `ui/session.py` — login, logout, the cookie.
- `ui/overview.py` — `/ui` and the sync button.
- `ui/jobs.py` — the runs view and cancel.
- `ui/nodes.py` — the topic page, its edits and its surgery.
- `ui/views.py` — graph, triage, activity, config.
Pure moves and import fixups. No route path, no template and no behaviour
changes.

## Acceptance criteria
- [x] Every route answers at the same path, with the same role.
- [x] `server/app.py` changes by imports only.
- [x] No module over ~250 lines.
- [x] The wheel still ships the templates.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-27 po: authored. The dashboard shipped; this is the tidy-up its own
  growth earned, taken now rather than left for whoever adds route 22.
- 2026-09-27 dev: `server/ui.py` (850 lines) became `server/ui/` — `__init__`
  131, `session` 57, `overview` 46, `views` 259, `nodes` 350, `jobs` 106.
  - One router, in `__init__`, with the shared pieces beside it: `_fields`,
    `LoginRequired`, the three role dependencies, `templates`, `_trees`,
    `_shape`, `_back`. The view modules are imported at the BOTTOM of
    `__init__`, which is what registers their routes — they import it back for
    the router, so the order is not a style choice.
  - `app.py` is unchanged: it already imported `LoginRequired` and `router`
    from `hrono.server.ui`, and both still resolve.
  - Verified by ROUTE TABLE, not by the suite alone: all 21 paths print with
    the module they now live in, and every one is where it was. Also checked
    the wheel ships the seven package files and the ten templates — a package
    rename that builds and ships nothing is the failure worth one check.
  - Gate: 1404 passed, 2 skipped.
- 2026-09-27 qa: verified. Pure moves; no test changed at all, which is the
  claim a behaviour-preserving split should be able to make.
