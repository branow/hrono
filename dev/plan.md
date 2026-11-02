# Plan: the insights step, and the small E054 fixes
Approved: 2026-11-02 (/autodev:run go)
Estimate (left): 3 epics and a second acceptance, about 3.45 h and 600k
output tokens, 1 at a time (E062 0.85 + E063 0.55 + E064 1.3 + acceptance
0.75; 160k + 110k + 180k + 150k).
First approved: 6 epics, 8.85 h, 1.39M; spent so far 806k on E055-E061 and
acceptance 1. Acceptance 1 failed O2 and the 390 bar and found 5 more gaps;
E062-E064 fix them (D14), adding 2.7 h and 450k plus 0.75 h and 150k for
acceptance 2.
Based on: this run's epics, 20-45 min each from start to merge (median 37,
board log) and 115k tokens per merged epic; E062 adds real passes to verify,
E064 a likely rework round (the cause of the second sync's moves is unknown).
Machine now (plan after acceptance 1): on battery, load 5 on 8 cpus, 4.4 GiB
free, so one epic at a time.

| # | Epic | What the user gets | Outcome | Tickets | Hours (build + verify + merge + rework) | Tokens |
|---|------|--------------------|---------|---------|------|--------|
| 1 | E055 (done) | upper briefs name every child and their shared rules; a copying brief is caught | O5 asked | 2 | 0.5 + 0.4 + 0.1 = 1.0 | 150k |
| 2 | E056 (done) | a sync places new sections where a build would; older installs get current prompt defaults | O6 asked | 3 | 0.6 + 0.4 + 0.1 = 1.1 | 170k |
| 3 | E057 (done) | insights role and tree settings; the dry run says which topics and what cost | O1 asked | 2 | 0.6 + 0.3 + 0.1 = 1.0 | 170k |
| 4 | E058 (done) | a pass reviews a subtree and extends its brief; pins kept; off = same tree | O1-O3 asked | 3 | 0.75 + 0.6 + 0.1 + 0.6 = 2.05 | 300k |
| 5 | E059 (done) | a sync re-reviews a rewritten reviewed brief before its parent; root.md carries the root's findings | O3 asked | 3 | 0.65 + 0.65 + 0.1 + 0.5 = 1.9 | 300k |
| 6 | E060 (done) | the dashboard shows the cost, the extension, the findings and Usage | O4 asked | 3 | 0.85 + 0.4 + 0.1 + 0.6 = 1.95 | 290k |
| 7 | E061 (done) | every tree's sync places by condensations; a failed pass shows on its topic | O6, O4 asked | 2 | 0.6 + 0.35 + 0.1 = 1.05 | 150k |
| 8 | E062 | turning insights on and pressing Review now runs the named reviews, root included; findings link the version read; README | O2, O1, O4 asked | 3 | 0.45 + 0.35 + 0.05 = 0.85 | 160k |
| 9 | E063 | a reviewed topic fits a phone; bad thresholds get a field error | O4 asked | 2 | 0.3 + 0.2 + 0.05 = 0.55 | 110k |
| 10 | E064 | an upgrade's first sync is announced with its cost, the next is free; a changed source url is fetched; steady events test | O5, O6 asked | 3 | 0.5 + 0.35 + 0.05 + 0.4 = 1.3 | 180k |
Then: acceptance 2 as a new user on the flask copy (about 0.75 h, 150k).

Order (one at a time): E057, E058, E056, E059, E060, E061 (done), then
E062 (O2 fails without it), E064, E063.

Model calls: qa spends at most 10 real claude-code subscription calls per
epic (D2), on the flask copy and the stored xgboost/bcreg trees; no rebuild.

Not in this plan (proposals): none.
Needs you:
- Q1-Q3 in questions.md (the run goes on with the recommended answers).
- Human checks: the bcreg rebuild and agent runs (501-505, 511 at scale;
  `backlog/bcreg-rebuild-checks.md`); insights on the private corpus in
  `~/hrono-private`; one pass on a metered Anthropic key to confirm the cost.
