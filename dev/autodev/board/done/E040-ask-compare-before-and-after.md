---
id: E040
title: re-asking a past question shows what changed since last time
priority: medium
depends_on: []
requirements: [34]
---

## Goal
The Ask page already keeps recent questions (cookie). A curator fixing the
tree wants to re-run one and see whether the answer got better: which passages
are new, gone, or moved.

## Tickets

### 401 a past question keeps what it returned and a re-run shows the change
Change: with each history entry keep a compact snapshot of its result (top
passage ids + scores, small enough for the existing per-browser store; no
migration). Re-running a history question marks each passage new / moved
(old rank) / same, and lists the ones that dropped out.
Done when:
- [ ] after a rebrief, re-asking marks the new and dropped passages correctly
- [ ] a corrupt or oversized stored history is ignored, never a 500
- [ ] the page says the history lives in this browser only
Look at: src/hrono/server/ui/ask.py (_history), templates/ask.html

## Out of scope
- server-side or shared question history
- recall usage by agents (E042)

## Log
- 2026-10-04 po: created from REQUIREMENTS 34 (history exists; compare is missing).
- 2026-10-04 dev: round 1 started, worktree .claude/worktrees/E040
- 2026-10-04 dev: 401 3fc4a85; tests/server/test_ui_ask.py (compare, corrupt/oversized, legacy, loading, long q) + browser suite pass; mutations killed: oversize guard, same, dropped, trim, key range, bool score, keep-on-loading, question cap
- 2026-10-04 qa: round 1 FAIL at 3fc4a85; drove Ask in Chromium against a built tree (new/dropped compare works); re-ran dev's dropped mutation (killed) and mine: trim-oldest-question (killed), drop score rounding (survived, minor); blocking: a history cookie holding a 400-digit integer score gives a 500 (OverflowError in ask_history._seen); followups in backlog/E040-followups.md
- dev round 2: ba456cd fixes the huge-int/NaN/Infinity score 500 via _finite; tests huge-int, nan, inf, overflow-float params; mutation removing isfinite check killed (3 fail), OverflowError guard covered by huge-int.
- 2026-10-04 qa: round 2 PASS at ba456cd; round-1 blocker fixed; drove Ask in Chromium against a built tree with huge-int, NaN and Infinity history cookies (all 200, snapshot dropped, re-ask then compares 'same'); re-ran dev's isfinite mutation (killed, 3 fail) and mine: OverflowError catch disabled (killed by huge-int); minors unchanged in backlog/E040-followups.md
- 2026-10-04 po: REJECT at ba456cd; user asked to apply all suggestions, so the 5 qa followups are required on this branch (see reject note); followups file moved to archive/.
- round 3 dev dec1bbf: all five followups done (real store_brief rebrief tests, round tested, label cut at /, hint above history, changed status). Mutations on round, label, changed, dropped, hint all fail tests. Ask/browser tests pass; full -n auto 2377 passed in 105s on a busy shared machine.
- qa round 3 pass at dec1bbf: all five PO changes checked; drove Ask in Chromium (hint on a first visit, an edited passage marked changed and counted '0 new, 1 changed, 0 dropped out', nothing listed as dropped, phone width); re-ran dev's mutations (changed branch, dropped exclusion, label guard, rounding) plus mine (place hashed from the full uri), all killed; full suite -n auto 62s at load ~35, same as main's 61s at the same time; followups in backlog/E040-followups.md.
- 2026-10-04 po: REJECT at dec1bbf; user asked to apply all suggestions, so qa round-3 followup (label still cut mid-word for a file name > 24 chars) is required; followups file folded into archive/.
- 2026-10-04 po: workflow marked stuck after 3 rounds; one blocker left (label cut mid-word, ask_history._label). No user question: the user asked to apply all suggestions, so restarted for that one fix.
- 2026-10-04 dev round 1 (restart): label for a file name > 24 chars shows the whole name; test_a_long_file_name_is_shown_whole_not_cut_mid_word; mutation (keep the cut tail) killed; Ask tests pass.
- 2026-10-04 qa restart round 1 PASS at 71391c2: label blocker fixed (whole file name when the cut tail has no /); ruff clean, test_ui_ask + test_ui_find 70 pass; drove Ask through the panel with a passage renamed to an 80-char file name then moved, rendered in Chromium at 375 and 1280 (dropped list shows the whole name); re-ran dev's mutation (drop the else, killed) and mine (tail = path, tail = rpartition[0], both killed); followups in backlog/E040-followups.md.
- 2026-10-04 po: REJECT at 71391c2; user asked to apply all suggestions, so both qa restart followups are required: dropped-label overflow at 375px (ask.html:94) and flat _label (ask_history.py:169); followups folded into archive/.
- qa round 2 PASS at ba9a313: both PO findings fixed. `#dropped li { overflow-wrap: anywhere; }` is in base.html; the 375px Chromium test fails without it (mutation re-run). `_label` returns early and behaves as before (diffed the logic); mutating the bare-file-name return fails test_a_long_file_name_is_shown_whole_not_cut_mid_word. ruff clean; 58 browser/ask tests pass. One minor followup is in backlog/E040-followups.md (attribution trailer in the commit body).
- 2026-10-04 po: REJECT at ba9a313; code and docs pass, but merge is ff-only so qa's followup (Co-Authored-By trailer in ba9a313's body) would land on main; user asked to apply all suggestions: reword ba9a313 to its subject line only, no code change; followups folded into archive/.
- 2026-10-04 qa round 3 PASS at 21cd2de: PO finding fixed. 21cd2de is ba9a313 reworded: same parent (71391c2), identical tree (92ee598), so the round-2 gate (ruff, 58 browser/ask tests, mutations) stands unchanged; message is the subject line only; `git log --format=%B main..epic/E040` shows no Co-Authored-By or body on any of the 5 commits; main is an ancestor (ff-only ok). No followups.
- 2026-10-04 po: ACCEPT at 21cd2de; every Done-when met per qa (rebrief compare, corrupt/oversized ignored, browser-only hint), all applied suggestions in, README matches, no trailers, ff-ok.
- merged to main at e49e87d
