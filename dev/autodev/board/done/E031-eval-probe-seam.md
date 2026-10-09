---
id: E031
title: the eval's probe is injected, and the README names every redacted output
priority: low
depends_on: [E029]
requirements: []
---

## Goal
Minor findings on E029: the redaction test stops monkeypatching a module
global, and the README lists the stderr report it now redacts.

## Tickets

### 1 main takes an injectable probe
Change: give `main` a probe parameter (as `check_isolation` has) defaulting to
the real one; the test passes a fake instead of monkeypatching `run._probe`.
Done when:
- [ ] the test uses no monkeypatch of `_probe` and still fails if either redact call is dropped
Look at: .e2e/eval/run.py:163, tests/eval/test_export_eval.py:679

### 2 the README names the redacted stderr report
Change: the redaction sentence lists the report, `isolation.json`, and the
stderr isolation report on a failed probe.
Done when:
- [ ] .e2e/eval/README.md:98 names all three
Look at: .e2e/eval/README.md

## Out of scope
- redacting anything beyond email addresses

## Log
- 2026-10-04 po: created from backlog/E029-followups.md (qa).
- 2026-10-04 dev: T1+T2 committed 13ddd14; tests/eval 49 pass; mutations: dropping either redact call fails the test.
- 2026-10-04 qa: pass at a4c7e50; tests/eval 49 pass, ruff clean; drove run.py CLI with a stub claude quoting an address: isolation.json and stderr redacted; 3 mutations fail the test; followups in backlog/E031-followups.md.
- 2026-10-04 po: plan — file was split across verifying/ and po-review/ by a stopped run; merged here; restarting for PO review.
- 2026-10-04 qa: pass at a4c7e50 (re-gate after restart); tests/eval 49 pass, ruff clean; drove run.py CLI with a stub claude quoting leak@example.com: exit 2, isolation.json and stderr redacted; mutations re-run: either redact call dropped, main not forwarding probe - all fail the test; minors unchanged, already in archive/E031-followups.md.
- 2026-10-04 po: accept at a4c7e50; both Done-when met (probe injected, no monkeypatch; README names all three); minors already in archive/E031-followups.md.
- merged to main at 5dad57a
