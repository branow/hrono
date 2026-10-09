---
id: E029
title: every eval output is redacted, and a test says so
priority: low
depends_on: [E028]
requirements: []
---

## Goal
E028 redacts reports, but one output path is untested and one (stderr) is not
redacted at all. Close both so no eval run can print the operator's address.

## Tickets

### 1 every isolation output goes through redact, pinned by tests
Change: run `render_isolation` output through `redact()` (stderr print on a
failed probe, run.py:168); add a test that runs `main` with a fake probe whose
reply quotes an address and asserts neither `isolation.json` nor stderr holds it.
Done when:
- [ ] dropping either `redact(...)` call (run.py:165, the stderr print) fails a test
Look at: .e2e/eval/run.py (main, render_isolation, redact), tests/eval/test_export_eval.py

### 2 README states what redaction does not catch
Change: .e2e/eval/README.md says injected context that is not email-shaped
(e.g. a company name) is neither probed nor redacted; reflow line 36 to 80 cols.
Done when:
- [ ] the limit is stated in one or two lines; no README line over 80 columns
Look at: .e2e/eval/README.md

## Out of scope
- probing for arbitrary non-email user context (company names)

## Log
- 2026-10-04 po: created from backlog/E028-followups.md (qa E028); commit-split line waived as process.
- 2026-10-04 dev: round 1 started, worktree created
- 2026-10-04 dev: T1 2fac532 test_a_failed_probe_quoting_an_address_reaches_neither_file_nor_stderr; mutated stderr redact and isolation.json redact, each failed it. T2 5b7be61 readme limit + reflow, no line over 80.
- 2026-10-04 qa: pass at 5b7be61; drove run.py CLI with a fake claude on PATH quoting an address: exit 2, stderr and isolation.json show [email redacted], no address; re-ran dev's two mutations (each redact dropped -> test fails) and own (redact substitutes empty -> test fails); ruff clean, tests/eval 49 passed; followups in backlog/E029-followups.md.
- 2026-10-04 po: accept at 5b7be61; both Done-when met per qa (each redact mutation fails the test, README limit stated, no line >80). qa's two minors stay in backlog/E029-followups.md.
- merged to main at 5b7be61
