---
id: E001
title: the condensation gate holds on a corpus of any size
priority: high
depends_on: []
requirements: [96]
---

## Goal
#221 landed on main (405edba, 412e229) with qa's last kickback open: `pending`
now binds every pending hash as a SQL parameter, so a first build over more
than 32,766 sections cannot condense at all. Close it and do the owed e2e.

## Tickets

### 1 pending never binds one parameter per section
Change: select bodies set-based (`NOT EXISTS` for missing, plus the
talking-back hashes chunked below the limit or via a temp table).
Done when:
- [ ] `pending` over > 32,766 never-condensed sections returns them all
- [ ] still reads no body it will not condense (existing trace test passes)
- [ ] mutation: reintroducing the single IN list fails the new test
Look at: src/hrono/summarize/store.py; archive/221 (qa log)

### 2 the e2e qa owed
Change: none expected — drive it.
Done when:
- [ ] on a copy of the local test database: list shows the 4 bad condensations, one
  sync re-condenses exactly those and rewrites only the briefs above them
Look at: `GET /trees/{n}/unusable-condensations`

## Out of scope
- the brief gate (#217, done)

## Log
- 2026-10-03 po: created from #221's open kickback.
- 2026-10-03 dev: round 1 started on epic/E001.
- 2026-10-03 dev: T1 efe8e40; 32,800-section pending test + lowered-limit listing test; mutations (IN list back, redo leg dropped, NOT EXISTS flipped, listing IN list back) all fail. Full suite 1686 green before the listing fix; summarize+server 579 green after.
- 2026-10-03 dev: T2 blocked: copying the local test database's master.key to a scratch copy was denied by the permission classifier; the e2e needs it (the re-condense calls the stored Anthropic connection).
- 2026-10-03 po ruling: T2 split. Do not retry the key copy; agents never touch the local test database's secrets. T2a (dev, blocks merge): fresh scratch home, own generated key, real `hrono serve`, small built tree with 4 planted talking-back condensations; over HTTP the list shows exactly those 4 and one sync re-condenses only them and rewrites only their ancestor briefs (real provider if a key is in env, else a local stub endpoint). Evidence in evidence/E001/.
- 2026-10-03 po ruling: T2b (user, does not block merge): the same check on a copy of the local test database against the merged head; dev writes the exact commands to evidence/E001/live-check.md and po raises it as needs-user at review.
- 2026-10-03 dev: T2a found a defect: `update` ran condense only when a source changed, so a sync over an unchanged corpus never re-condensed the listed condensations. Fixed in f3e4853 (condense also runs when the condense model holds a talk-back); new unit test; mutations (guard reverted, no-model branch raising) both fail. Gate: 1688 passed.
- 2026-10-03 dev: T2a e2e green on f3e4853: fresh home + generated key, real `hrono serve`, local openai-compatible stub, 6-topic corpus; list showed exactly the 4 planted, one sync re-condensed exactly those 4 and rewrote briefs 1,2,7 (their 2 topics + root); 44 condensations and briefs 3-6 byte-identical; 7 LLM calls. evidence/E001/transcript.md, node-diff.json, transcript-before-fix.md (same run on efe8e40: 0 re-condensed); driver and stub beside them.
- 2026-10-03 dev: T2b commands in evidence/E001/live-check.md. Filed backlog/short-talk-back-condensation-passes-the-gate.md.
- 2026-10-03 qa: PASS round 2 on f3e4853. Gate: ruff clean, 1688 passed/4 skipped. Re-ran the T2a driver from a clean qa worktree (fresh home, generated key, real `hrono serve`, stub): list = exactly the 4 planted, one sync re-condensed exactly those 4, rewrote briefs 1,2,7 only, 44 condensations + briefs 3-6 byte-identical, 7 calls, list empty after. Mutations: dev's guard revert fails; mine: always-condense fails; trigger-on-any-condensation survives (equivalent: pending is empty, no call, no credential). live-check.md commands checked against the sync record shape. Backlog: update-stage-hides-its-condense-outcome, persistent-talk-back-costs-every-sync.
- 2026-10-03 po: ACCEPT f3e4853. T1 met (32,800-section test, mutations fail); T2a met by dev+qa e2e over real `hrono serve` (exactly 4 re-condensed, briefs 1,2,7 only). T2b left to the user: run evidence/E001/live-check.md against the merged head; does not block merge.
- 2026-10-03 dev: merged to main, head f3e4853 (rebase clean, gate green: 1688 passed).
