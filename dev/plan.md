# Plan: the insights step, and the small E054 fixes
Approved: 2026-11-02 (/autodev:run go)
Estimate: 6 epics, about 8.85 h of agent time (8.1 h of epics + 0.75 h
acceptance) and 1.39M output tokens; E055 is done (about 0.4 h), so 7.85 h
and 1.24M are left. Ticket 3 of E056 (older prompt defaults, from E055 qa)
adds 0.15 h and 20k.
Based on: the no-history figures (no epics since 2026-11-01), plus the
verify time of real model calls (a pass is 34-45 turns) and one rework
round on E058 and E060
Machine now (2026-11-02, plan after E060 r2 review): on battery, load 20 on
8 cpus, 4.4 GiB free, so one epic at a time. Done: E055-E059; E060
accepted again at cbec433 after a merge conflict with E059's test (merging). E061 added: defects qa found in O6 (a sync
of the default tree places on two vector spaces) and O4 (a pass failing on
a provider error shows no callout), with E060's small followups; +1.05 h,
+150k. It starts once E060 is on main (it changes E060's files).
Left: E061 and acceptance: about 1.8 h and 300k tokens.

| # | Epic | What the user gets | Outcome | Tickets | Hours (build + verify + merge + rework) | Tokens |
|---|------|--------------------|---------|---------|------|--------|
| 1 | E055 (done) | upper briefs name every child and their shared rules; a copying brief is caught | O5 asked | 2 | 0.5 + 0.4 + 0.1 = 1.0 | 150k |
| 2 | E056 (done) | a sync places new sections where a build would; older installs get current prompt defaults | O6 asked | 3 | 0.6 + 0.4 + 0.1 = 1.1 | 170k |
| 3 | E057 (done) | insights role and tree settings; the dry run says which topics and what cost | O1 asked | 2 | 0.6 + 0.3 + 0.1 = 1.0 | 170k |
| 4 | E058 (done) | a pass reviews a subtree and extends its brief; pins kept; off = same tree | O1-O3 asked | 3 | 0.75 + 0.6 + 0.1 + 0.6 = 2.05 | 300k |
| 5 | E059 (done) | a sync re-reviews a rewritten reviewed brief before its parent; root.md carries the root's findings | O3 asked | 3 | 0.65 + 0.65 + 0.1 + 0.5 = 1.9 | 300k |
| 6 | E060 (accepted, merging) | the dashboard shows the cost, the extension, the findings and Usage | O4 asked | 3 | 0.85 + 0.4 + 0.1 + 0.6 = 1.95 | 290k |
| 7 | E061 | every tree's sync places by condensations; a failed pass shows on its topic | O6, O4 asked | 2 | 0.6 + 0.35 + 0.1 = 1.05 | 150k |
Then: acceptance as a new user on the flask copy (about 0.75 h, 150k).

Order (one at a time): E057, E058 (critical path to the insights outcomes),
then E056 (needs nothing, starts while E058 merges), E059, E060, E061.

Model calls: qa spends at most 10 real claude-code subscription calls per
epic (D2), on the flask copy and the stored xgboost/bcreg trees; no rebuild.

Not in this plan (proposals): none.
Needs you:
- Q1-Q3 in questions.md (the run goes on with the recommended answers).
- Human checks: the bcreg rebuild and agent runs (501-505, 511 at scale;
  `backlog/bcreg-rebuild-checks.md`); insights on the private corpus in
  `~/hrono-private`; one pass on a metered Anthropic key to confirm the cost.
