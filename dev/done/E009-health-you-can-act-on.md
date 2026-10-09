---
id: E009
title: fix what the health page shows, from the health page
priority: medium
depends_on: [E007]
requirements: [47, 48, 49, 50, 59]
---

## Goal
"Needs attention" is counts that link elsewhere, though the API can already
place a parked section and rewrite a stale brief. Put the action beside the
problem. Detail: archive/218.

## Tickets

### 1 parked sections and misfits, placed by hand
Change: each item opens to its list; parked: nearest topic and score, place
into a chosen topic (existing move endpoint, which pins); misfits: move.
Done when:
- [ ] a placement made from the list survives a sync
Look at: server/ui/nodes.py, templates/triage.html, edits.py

### 2 regenerate one stale brief
Change: show why it is stale; scope brief/brief-upper to one topic if the op
lacks it.
Done when:
- [ ] regenerating one brief rewrites only that topic — asserted on what changed
Look at: src/hrono/summarize/brief.py, brief_upper.py

### 3 hand edits and who fixes what
Change: list every pinned topic/section with release; each item says whether
the next sync deals with it or a person must.
Done when:
- [ ] reader sees lists only; forged POSTs refused
- [ ] driven in a browser on a tree with each condition
Look at: pins.py

## Out of scope
- undo / brief history (optional lines 60, 61)

## Log
- 2026-10-03 po: created from #218.
- 2026-10-03 po: starting (E011 merged; touches nodes.py/triage.html/summarize/pins, no overlap with E008 or E022; E010 waits on nodes.py).
- 2026-10-03 dev: round 1 started, worktree epic/E009.
- 2026-10-03 dev: T2 f2e4d86: node scope on brief/brief-upper, test_brief_scope.py; mutants only=None in both ops killed.
- 2026-10-03 dev: T1+T3 b1f1e00: Health lists + place/regenerate/release (admin-only), test_ui_health.py; mutants (release tree check, tree join, role, can_write, op choice, skip-own-topic) all killed; driven in Chromium as admin and reader, evidence/E009/.
- 2026-10-03 qa: round 1 FAIL at b1f1e00: settled-echo brief listed as sync-fixed and its Rewrite runs a no-op job; tickets 1+3 share one commit; README calls forced placements misfits; stale_why contract. Drove Health in Chromium as admin/writer/reader at 1440/800 (place, move, release, regenerate, forged 403s); re-ran only=None mutant (killed), own id>=? and dropped forced=1 mutants (killed).
- Round 2 (5096c18): settled echo now says a person must write it, no button (briefs.settled, tested in unit and UI; mutation dropping _rewritable killed); stale_why contract narrowed; README and copy fixed. Commit split of b1f1e00 not done: qa has seen it and rewriting seen commits is barred.
- 2026-10-03 qa: round 2 PASS at 5096c18: settled echo row says a person must write it with no button, plain stale row still rewrites (job scope node 2); stale_why contract narrowed; README rewrapped. Drove Health in Chromium as admin and reader at 1440/800, no overflow. Re-ran dev's dropped-_rewritable mutant (killed) and own: dropped member_signature check, dropped stale check, button shown always, attention passes False (all killed). Open for PO: b1f1e00 still holds tickets 1+3; dev rules bar the split (backlog/commit-split-after-qa-has-seen.md).
- 2026-10-03 po: review REJECT at 5096c18: Health summary still promises a sync rewrites every listed brief (triage.py:122, contradicts the settled-echo row; req 50; folds backlog/health-summary-settled-echo.md); README omits placing a waiting section. Commit split waived.
- dev round 3: 05e8786 Health summary no longer promises a sync when a listed brief is a settled echo (both cases tested, mutation bites); README says admin places a waiting section.
- qa round 3 @05e8786: FAIL. Both PO fixes are in and their tests bite (forcing the sync wording, and counting every missing brief as settled, each fails a test); 765 affected tests pass. Three small findings remain: triage.py:119-120 adds an inline comment citing requirement 50, against CONTRIBUTING's no-new-comments rule; the page reads "1 need a person" with no singular form; README.md:97 is 110 columns, not rewrapped.
- 2026-10-03 po: stuck after r3 on three mechanical findings (drop triage.py:119-120 comment; "1 needs a person" singular + test; rewrap README 92-99). needs-user: grant one more dev round? (rec: yes)
- 2026-10-03 po: user answered "yes": one more dev round — drop triage.py:119-120 comment, "1 needs a person" + test, rewrap README 92-99. Restarting.
- dev round 4: 622e39e singular "1 needs a person" (test bites when mutated), triage.py comment dropped, README rewrapped.
- 2026-10-03 qa round 4 @622e39e: FAIL. All three r3 findings are fixed (comment gone, README rewrapped to 80, "1 needs a person" whose revert-to-need mutant fails a test); 831 affected tests pass, format and lint clean. One finding: the plural arm of triage.py:124 is untested; mutating it to always "needs" passes all 28 Health/triage tests (a population of ONE, CONTRIBUTING:33). Needs a test with two settled echoes asserting "2 need a person".
- dev round 2: 35dbd83 plural arm tested (two settled echoes, '2 need a person'); mutating to always 'needs' fails it.
- 2026-10-03 qa round 5 @35dbd83: PASS. The r4 finding is fixed: test_several_settled_echoes_say_need_a_person asserts "2 need a person". Re-ran dev's always-'needs' mutant (killed) and my own any()-capped count (killed); 657 affected tests pass (40 files, xdist), format and lint clean. Not re-driven in a browser since only a test changed; r2 drove Health as admin and reader.
- 2026-10-03 po: review ACCEPT at 35dbd83: all Done-when met per qa r2/r5 (placement survives sync, one-topic regenerate, reader lists only, forged POSTs 403, browser-driven); my r2 findings fixed (summary wording, README); commit split waived.
- merged to main at 421a0df (rebased, full suite green)
