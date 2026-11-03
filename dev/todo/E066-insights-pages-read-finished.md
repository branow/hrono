---
id: E066
title: the insights pages read as finished, and the upgrade notice prices the sync right
priority: high
kinds: [ui, backend, infra]
depends_on: [E065]
outcomes: [O4, O2, O5]
journeys: [J6, J7]
waits_on: []
---

## Goal
Acceptance 2 (`dev/acceptance/2026-11-03-1501-1.md`) passed every outcome
on the flask copy but left six gaps a curator or contributor sees: a
confidence chip that contradicts its text, raw backticks in findings, a
settings line with "reviewed.." and a billing note when nothing would run,
a review run titled as placement, an upgrade notice priced at half the real
cost (and to four decimals), and two fast-suite tests that go red under
load. This epic closes them so the run can end on a clean acceptance (D19).

## Build on
- Inline code: the brief above already renders Markdown; reuse its filter
  (escape first, then backtick spans only) for statement, confidence prose
  and placement. Rejected: full Markdown in findings (headings, links).
- Price: `price.cost(input, output, cache_write, cache_read)` already takes
  cache tokens; measure the cache-write share from this tree's own brief
  ledger rows, as `_priced` does for output (`src/hrono/health/upgrade.py:171`).
- Run title: the job's stage counts already say what ran (`Stages: review`).
- Flakes: widen the heartbeat test's grace by waiting on the condition, not
  a fixed window; scope the ResourceWarning check to the connection the
  delete preview opened (or run it in its own process), not global gc.

## Design
- Chip: one of high, medium-high, medium, low-medium, low (uk through `_()`);
  a range takes the lower level's tone; the prose after it starts with no
  stray "high:". Unknown levels: no chip, the whole text as prose.
- Settings, nothing due: "Every topic over the threshold has been reviewed;
  a sync reviews a topic again when it rewrites its brief." One sentence, no
  billing note, no Review now. uk the same meaning.
- Run title for a settle that only reviewed: "review the topics that were
  due"; a settle that placed sections keeps today's title.
- Money in every estimate (upgrade notice on Home and Health, insights line)
  to cents: "about $1.66".

## Tickets

### 1 findings, settings line and run title read right
Done when:
- [ ] flask copy, topic 17 after `hrono tree review`: the "medium-high"
      finding shows a "medium-high" chip and prose "relies on ..."; no
      finding shows a backtick, identifiers render as code as in the brief;
      390 and 1440, light and dark, en and uk
- [ ] a statement holding `<script>` renders as text, not markup (test)
- [ ] Settings for flask with every topic reviewed shows the one sentence
      above: no "..", no subscription note, no Review now
- [ ] the Runs page of that review run is titled "review the topics that
      were due"; a sync's settle keeps "place the sections ..."
Look at: src/hrono/server/ui/reviewed.py:19, templates/node.html:153,
templates/config.html:192, src/hrono/server/ui/jobs.py:74

### 2 the upgrade notice prices the first sync within its "about"
Change: `_priced` counts cache-write (and read) tokens at the table's
prices; every shown estimate rounds to cents. `hrono tree review` on a
provider error names the failed item ("review of topic 17").
Done when:
- [ ] a fresh copy of the flask bench db (built 10 Oct): Home and Health
      say about 25 calls and a cost within 25% of what Usage shows after
      the sync (~$1.66 last time), written to cents
- [ ] a fake provider answering 500 to the insights model: `hrono tree
      review flask` prints the failed topic with the error
Look at: src/hrono/health/upgrade.py:171, templates/_parts.html (rewrite
hint), src/hrono/tree/commands.py:104

### 3 the fast suite stays green under load
Done when:
- [ ] `test_health_depends_on_the_beat_actually_coming_round` and
      `test_the_delete_preview_closes_its_copy` pass 20 runs in a row with
      the machine loaded (`-n auto` beside a second `-n auto` suite run)
- [ ] the fast suite stays under 90 s
Look at: tests/jobs/test_worker.py, tests/registry/test_completeness.py

## Out of scope
- POST /jobs other ops on an unknown tree; Home's 0.55 s plan query on
  bcreg; ui-check reading undrawn closed disclosures (autodev tool).

## Tried

## Log
- 2026-11-03 po: created from acceptance 2's six gaps (D19), with the
  cents rounding (E064 followups) and the CLI failure line (E065 followups).
