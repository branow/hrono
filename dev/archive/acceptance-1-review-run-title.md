# A review run is titled as a placement run (acceptance 1 rerun, 2026-11-03)

What the user did: ran `hrono tree review flask`, opened the run on Runs.
What happened: the run page heads it "settle - place the sections that were still waiting",
while it only reviewed two topics (Stages: review).
Expected: a title that says what ran, e.g. "review the topics that were due" when the settle
only reviewed (already listed in backlog/E065-followups.md; confirmed on the real app).
Where: src/hrono/server/ui/jobs.py:74.
Evidence: dev/evidence/acceptance-1/2026-11-03/ui/ui-jobs-job-ea50b03c*.png
