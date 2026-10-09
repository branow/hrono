---
id: E028
title: the eval isolation probe catches injected user context
priority: low
depends_on: [E027]
requirements: []
---

## Goal
The export eval says "isolation verified" while the isolated session still
sees the harness-injected user context (the operator's email), which then
lands in evidence reports. Verified must mean no operator context at all.

## Tickets

### 1 the probe fails on any injected user context
Change: `isolation_verdict` also fails when the isolated reply carries the
harness user-context block (e.g. a `userEmail` entry), not only the CLAUDE.md
canary and a word from the operator's own config; the runner isolates it out if the CLI allows, else
refuses to run without `--allow-unisolated`.
Done when:
- [ ] a unit test: an isolated reply quoting a userEmail entry is not verified
- [ ] a real probe run: verified only when no user context is quoted
Look at: .e2e/eval/run.py (check_isolation, isolation_verdict, ISOLATION)

### 2 reports never carry the operator's email
Change: rendered reports redact an email-shaped string from model replies;
redact the existing `evidence/E027/*-report.md`.
Done when:
- [ ] no evidence report holds an email address
Look at: .e2e/eval/run.py (render), .autodev/board/evidence/E027/

## Out of scope
- changing the eval's arms or questions

## Log
- 2026-10-04 po: created from backlog eval-isolation-still-leaks-user-context (qa E027).
- 2026-10-04 dev: round 1 started
- 2026-10-04 po: orphaned by a stopped run (worktree clean, no commits); restarted on its branch.
- 2026-10-04 dev: T1+T2 in one commit 4e5c07b; unit tests plus real probe (haiku): isolated reply quoted the account email, so verified=False, as intended; mutated each of the 3 guards, each failed a test; E022/E027/E018 evidence redacted by sed.
- 2026-10-04 qa: pass at 4e5c07b; ruff clean, tests/eval 48 pass; drove the real probe on haiku through run.py: exit 2, verified=False, isolated reply quoted the account email, and isolation.json had it redacted; evidence/ scanned and holds no address; re-ran mutations: drop the report redact (killed), drop the EMAIL check (killed); my own, drop the isolation.json redact, survived (minor); followups in backlog/E028-followups.md.
- 2026-10-04 po: accept at 4e5c07b; both Done-whens met by qa's real probe and evidence scan; README states the limit; minors in backlog/E028-followups.md.
- dev merge: E028 landed on main at 4e5c07b (full suite 2309 passed)
