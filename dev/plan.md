# Plan: the insights step, and the small E054 fixes
Approved: (not yet; /autodev:run go)
Estimate: 6 epics, about 8.7 h of agent time (7.95 h of epics + 0.75 h
acceptance) and 1.37M output tokens; about 5.7 h on the clock, up to 3 at
once, because E057 -> E058 -> E060 run in turn
Based on: the no-history figures (no epics since 2026-11-01), plus the
verify time of real model calls (a pass is 34-45 turns) and one rework
round on E058 and E060
Machine now: 3.4 GiB free memory leaves room for 0 more agents
(a Playwright `adminchat.py` left running holds some); 2-3 at once once it
is freed

| # | Epic | What the user gets | Outcome | Tickets | Hours (build + verify + merge + rework) | Tokens |
|---|------|--------------------|---------|---------|------|--------|
| 1 | E055 | upper briefs name every child and their shared rules; a copying brief is caught | O5 asked | 2 | 0.5 + 0.4 + 0.1 = 1.0 | 150k |
| 2 | E056 | a sync places new sections where a build would | O6 asked | 2 | 0.5 + 0.35 + 0.1 = 0.95 | 150k |
| 3 | E057 | insights role and tree settings; the dry run says which topics and what cost | O1 asked | 2 | 0.6 + 0.3 + 0.1 = 1.0 | 170k |
| 4 | E058 | a pass reviews a subtree and extends its brief; pins kept; off = same tree | O1-O3 asked | 3 | 0.75 + 0.6 + 0.1 + 0.6 = 2.05 | 300k |
| 5 | E059 | a sync re-reviews a rewritten reviewed brief before its parent | O3 asked | 2 | 0.5 + 0.5 + 0.1 = 1.1 | 170k |
| 6 | E060 | the dashboard shows the cost, the extension, the findings and Usage | O4 asked | 3 | 0.75 + 0.4 + 0.1 + 0.6 = 1.85 | 280k |
Then: acceptance as a new user on the flask copy (about 0.75 h, 150k).

Order: E055, E056 and E057 start together; E058 after E057; E059 and E060
after E058.

Model calls: qa spends at most 10 real claude-code subscription calls per
epic (D2), on the flask copy and the stored xgboost/bcreg trees; no rebuild.

Not in this plan (proposals): none.
Needs you:
- Q1-Q3 in questions.md (the run goes on with the recommended answers).
- Human checks: the bcreg rebuild and agent runs (501-505, 511 at scale;
  `backlog/bcreg-rebuild-checks.md`); insights on the private corpus in
  `~/hrono-private`; one pass on a metered Anthropic key to confirm the cost.
