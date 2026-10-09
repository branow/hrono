---
id: E006
title: Settings — one collection at a time, forms a person can fill
priority: high
depends_on: []
requirements: [10, 65, 66, 67, 69]
---

## Goal
The user called Settings "terrible": five collections on one 3000px page, raw
config paths as labels, inline edit forms. Rebuild it on the same routes and
descriptor-driven forms. Detail: archive/210.

## Tickets

### 1 one collection per view, as a table
Change: sub-nav Trees, Sources, Connections, Models, Prompts; each a table with
real columns; add/edit open as their own view; keep JSON as "advanced".
Done when:
- [x] no page is longer than its content; add/edit never displace the list
Look at: server/ui/settings.py, templates/config.html

### 2 forms with human labels and help
Change: label + one-line help per field from the descriptor; inputs match type;
source fields grouped Location, Access, Which files.
Done when:
- [x] a test fails if a descriptor field lacks a label or help text
- [x] secrets are still never rendered back
Look at: src/hrono/registry (descriptors)

### 3 delete with its impact, completeness, environment
Change: delete is a row action leading to the impact preview; the page says
what is missing to build; read-only version, db path, LLM concurrency.
Done when:
- [x] delete shows the impact preview before confirming
- [x] a role with no model is reported as missing
- [x] screenshots 1440/800, light/dark, in evidence/E006/
Look at: registry/impact.py

## Out of scope
- the first-run wizard (E013)

## Log
- 2026-10-03 po: created from #210.
- 2026-10-03 dev: round 1 started on epic/E006.
- 2026-10-03 dev: T1 6df706c — sub-nav + tables + own-view add/edit/delete; tests through /ui/config, drove a real serve. Mutations: _showing ignoring edit/add/delete (16 fail), _settled dropping section (1 fail), delete mode never set (2 fail).
- 2026-10-03 dev: T2 7f0c1ac — title/description/examples/group on every registry field, read by forms.py; test_field_docs walks all 82 fields. Mutations: drop a description, help/label/example blanked, group not inherited, url back in ROOMY — each fails a test; dead name-first sort removed.
- 2026-10-03 dev: T3 ffcf798 — impact.of_delete + registry/completeness.py (same resolvers as the build; maintain shares BUILD_ROLES) + env block; drove real serve, 16 screenshots 1440/800 light/dark in evidence/E006. Mutations: reset-as-delete, no impact, no gaps, db path, unreachable x2, prompt check, named, model skip, prompt-hash and source filters — all fail a test.
- 2026-10-03 po: restarted — orphaned by a stopped run; resumes on its branch and worktree.
- 2026-10-03 qa: round 1 FAIL at ffcf798 — drove a real serve (tables, add/edit forms, connection/model/prompt delete previews, gaps, env block) and screenshots 1440/800; mutations re-run: _removal returning [] (2 fail), judge dropped from gaps (3), _unreachable inverted (4), label blanked (3), env-width source (1) — all killed. Findings: the delete preview's green "Nothing in any tree goes stale or stops working" is shown for a built tree's delete (beside the warning that the next maintain clusters the whole corpus into it) and for deleting the only model serving a role; stale test name test_a_delete_needs_the_box_ticked.
- round 2 fix 44589fe: tree delete shows no 'nothing' callout beside its note; model/prompt delete names roles left unserved via completeness.gaps before/after (savepoint); test renamed. Verified by 325 registry+ui tests; mutation dropping _unserved caught.
- 2026-10-03 qa: round 2 FAIL at 44589fe — round-1 findings 1 and 3 fixed, 2 fixed for models; drove a real serve (model/prompt/connection/source delete previews, preview under a held write lock); mutations: drop model _unserved (1 fail), drop before-filter (3), revert template guard (1), drop ROLLBACK TO (2) killed, drop prompt _unserved SURVIVED. Findings: the preview now takes the write lock on a GET (503 after 5s while any writer holds it); prompt half untested; deleting the only source still says nothing stops working.
- dev round 3: 2bb5e9e read-only after-gaps via in-memory registry copy for all collections, prompt/source/lock tests; mutations: no-delete and no-_unserved fail
- 2026-10-03 qa: round 3 PASS at 2bb5e9e — round-2 findings all fixed; drove a real serve: model/source delete previews list every refused role / "no source is registered to read" (screenshots), and the same previews under a held BEGIN IMMEDIATE return 200 in 0.02s (was 503 after 5.4s); 437 affected tests pass, ruff clean; mutations: revert to SAVEPOINT+DELETE (lock test fails), skip _unserved for sources (2 fail), drop before-filter (8 fail) — all killed. Non-blocking: completeness._registry_without restates the registry schema by hand and never closes its in-memory connection.
- 2026-10-03 po: ACCEPT at 2bb5e9e — every Done-when met per qa round 3 + evidence/E006; README and CONTRIBUTING updated; epic's 160 tests run in 9s. Follow-ups filed: backlog/registry-copy-restates-schema.md, backlog/suite-has-no-xdist.md.
- dev merge: landed on main at 026d8ea (full suite 1904 passed)
