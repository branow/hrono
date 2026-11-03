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
- 2026-11-02 dev round 1 started, worktree .claude/worktrees/E064
- 2026-11-03 dev: T1 (8322788, 63313c9) on a fresh copy of the bench db, text models repointed to a local fake openai-compatible server: Home and Health before sync name 19 briefs (older prompt), 287 sections moving, "about 25 calls"; sync made 25 text calls (20 brief, 5 brief-upper; ledger, embeddings excluded), 0% off. After it Home has no callout and Health "All clear". Survives restart (server restarted, callout rendered again). Screenshots 390/1440 light/dark in dev/evidence/E064 (ui-check overlaps are the shared header nav only). Tests: tests/server/test_ui_upgrade.py; mutation: `hash != prompt` flipped, 3 tests fail.
- 2026-11-03 dev: T2 (48be7f4) cause: the monitor and repair read vectors of condensations/briefs not yet embedded, so the first sync moved sections and the next moved more; fix: embed before monitor and a second repair after a split. Copy: sync 1 then sync 2 unchanged: 0 calls, 0 briefed, 0 moved. Test tests/tree/test_sync_chain.py twice-unchanged (0 calls); the toy tree does not exhibit the misfit so the mutation (drop the early embed) does NOT bite there, real-app run is the proof.
- 2026-11-03 dev: T3 (2b4b56b, a51eb47) url: `PUT /sources/flask` to a clone with one new commit then sync: changed true, cache head moved (copy); tests/ingest/test_git_sync_follows_the_url.py bites (set-url mutated: fails). Events test: waits on the stream, 20/20 under -n 4. Manual-split flake cause: the app's startup warms the encoder on a thread importing torch while UMAP runs; scipy sees a half-built torch, "reduction failed" (500). Fixed by importing torch at the test module top; 20/20 under -n 4. The identical-vector fixture was NOT the cause: 3 non-degenerate fixtures (blob, ring, line) split or flip under UMAP/HDBSCAN, so it is kept. Production has the same race (sync right after boot); see backlog.
- 2026-11-03 qa round 1: pass at 317990a. Drove a fresh bench copy (text models on a local fake): Home and Health named 19 briefs, 287 sections, about 25 calls (~$0.82 subscription estimate); Sync now made 28 text calls (20 brief, 8 brief-upper incl. 3 copy re-asks, 12% over), then Home and Health clear; sync 2 unchanged: 0 calls, 0 moved, 0 briefs; url edited to a clone with one commit: changed true, cache origin moved; hostile urls (empty, missing, --upload-pack, 10 KB, NUL) refused 400/422; uk Home read. Re-ran mutations: hash flip (3 fail), set-url removed (fails). Fixed: uk 'second sync' line (39a35a7); tests for the moving count and split calls, and the twice-unchanged test now bites on the early embed (317990a). Full suite green (1 browser flake, passes alone, backlog/flaky-test_a_live_run_with_a_stage_done_reads_running_never_partial.md). Manual-split Done when kept its identical-vector fixture: dev showed the flake was the torch import race, PO to note. Followups: backlog/E064-followups.md.
- 2026-11-03 po: reject round 1 (screens and counts good, 0 calls on sync 2). T2's Done when is not met for a tree that already holds a monitor baseline (any tree synced before the upgrade): the raw-vector baseline is kept, so `settle_due` can fire on the next unchanged sync. Round 2: reset the baseline on the vector-space change; `remote set-url --`; fix the boot torch race in the app instead of the test; steady the live-run browser test; Health hint margin.

- Round 2 (dev): baseline dropped when condensations get embedded (test fails without it); set-url takes -- (test fails without it); torch imported before worker start, importorskip dropped, test_manual_split 20/20 under -n 4; live-run badge test waits on the page, 20/20 under -n 4; rewrite hint gap in base.html. Fast suite 2172 passed.
- 2026-11-03 qa round 2: pass at 25b1458. Bench copy with a real raw-vector baseline (monitor on raw space: 0.0877), text models on a local fake: sync 1 right after boot succeeded, 27 text calls, baseline re-measured 0.1266, settle_due false; sync 2 unchanged 0 calls, 0 moved, 0 briefs, baseline kept; source url set to --upload-pack=touch <marker> in the registry: sync fails sync-error, no marker, then restored and synced clean. Re-ran mutations: drop_baseline removed (test fails), set-url '--' removed (test fails). Health hint gap seen at 1280/390 light/dark (ui-check; only the pre-existing skip-link header overlaps). Fixed: docs/clustering.md states the baseline reset (25b1458). Full suite green (2356 passed). Followups: backlog/E064-followups.md.
- 2026-11-03 po: accept round 2 at 25b1458. The raw-vector baseline is re-measured after the upgrade (bench copy: 0.0877 to 0.1266, settle_due false, sync 2 zero calls); `set-url --` refuses a hostile url; the boot torch race is fixed in the app; Health's rewrite card read at 390. Left in followups: the 0.55 s plan query, the long moving line, the 4-decimal cost.
- merged: main at eb82757
