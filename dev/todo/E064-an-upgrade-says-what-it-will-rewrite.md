---
id: E064
title: an upgrade says what its first sync will rewrite, and an unchanged source then costs nothing
priority: high
kinds: [backend, ui]
depends_on: [E062]
outcomes: [O5, O6]
journeys: [J4, J7, J3]
waits_on: []
---

## Goal
An admin who upgrades hrono sees Home "up to date", presses Sync now with
nothing changed in the source, and pays 54 then 8 model calls: every leaf
brief rewritten (this run changed the default `brief` prompt), 4 topics split
and 64 sections refiled (members moved from raw vectors to condensations,
O6), then 6 more sections migrated on the next unchanged sync (misfit above a
baseline measured on the old vectors). Nothing warned them (acceptance 1,
gap 5). A changed git source url is also silently ignored (gap 4), and a
full-suite test flakes (gap 7). After this epic the one-time rewrite is
announced with its cost before it runs, and a second unchanged sync is
quiet.

## Build on
- Health's stale briefs (`health/attention.py` `stale`, `briefs.stale_why`)
  and Home's up-to-date state: a brief written by an older prompt version
  or the raw-vector placement is a reason Health and Home already have a
  place for. Rejected: a new upgrade page or banner system.
- The registry dry run's "passes and cost" estimate (`registry/impact.py`)
  for the call count.
- The monitor baseline (`cluster/monitor.py`), reset when the placement
  vector space changes.
- `ingest/git_syncer.py` `git_sync`: set the cache's `origin` to the
  registry's `url` before fetching.

## Design
Home, when briefs are stale by prompt or the tree is on another vector
space: the up-to-date line becomes "16 briefs were written by an older
prompt; the next sync rewrites them (about 54 calls, ~$X estimate)" with the
existing Health link; Health lists the stale briefs with that reason. Copy
in GLOSSARY.md words, en and uk.

## Tickets

### 1 Home and Health say what the first sync after an upgrade rewrites, with its cost
Done when:
- [ ] on a fresh copy of `~/hrono-bench/db/hrono.db` (built 2026-10-10)
      served on main, before any sync: Home and Health name the briefs the
      next sync rewrites and why (older prompt; sections moving to
      condensation vectors) and the estimated calls; the estimate is within
      25% of the calls the sync then makes (every text model on the fake
      provider; count from the ledger, in the Log)
- [ ] after that sync, Home says up to date and Health lists none
- [ ] 390 and 1440, light and dark: Home with the line (screenshots)

### 2 a second sync with nothing changed moves nothing and calls nothing
Done when:
- [ ] on that copy after sync 1, sync 2 with nothing changed in the source:
      zero model calls, zero sections moved, zero briefs rewritten (cause
      and fix in the Log; the baseline after a vector-space change is
      measured on the new space)
- [ ] a tree built today and synced twice unchanged: zero calls both times
      (test)

### 3 a changed source url is fetched, and the events test is steady
Done when:
- [ ] `hrono sources set flask` to a clone carrying one new commit, then
      `hrono tree sync flask`: the new commit arrives (`changed: true`) with
      no hand edit of the cache (test with two local repos, and on the copy)
- [ ] `tests/jobs/test_events.py::test_the_stream_follows_a_job_to_its_end`
      passes 20 runs in a row under `-n auto` load (cause in the Log)
- [ ] `tests/server/test_manual_split.py::test_a_topic_that_does_not_divide_is_refused_and_left_intact`
      rests on a fixture that does not divide for a reason other than a
      degenerate UMAP of identical vectors; 20 runs in a row under
      `-n auto` (from `backlog/flaky-test_a_topic_that_does_not_divide_is_refused_and_left_intact.md`)

## Out of scope
- Making the prompt rewrite itself optional; the new prompts are wanted.

## Tried

## Log
- 2026-11-02 po: created from acceptance 1 gaps 4, 5 and 7 (O5, O6).
- 2026-11-02 po: the manual-split flake added to ticket 3 (seen again in E062's full run).
