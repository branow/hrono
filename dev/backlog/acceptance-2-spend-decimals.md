# acceptance 2: spend under $1 reads in four decimals

- Did: opened the review run (`/ui/jobs/job_4a50...`) and Usage after one review.
- Got: "Cost ~$0.9081 est.", stage rows "~$0.0613", "~$0.8468"; Usage by day/model the same.
  At 390 the run page's Cost column is cut at the card edge (the table scrolls sideways).
- Expected: cents, as Home ("~$2.41") and the upgrade notice ("about $1.58") show; "<$0.01"
  for less (the rule `setup.dollars` got in E066).
- From: `src/hrono/usage/present.py:26` (E066 followup). Evidence:
  `dev/evidence/acceptance-2/2026-11-03/ui/ui-jobs-*-390-dark.png`, `ev/o4-run-page.txt`.
