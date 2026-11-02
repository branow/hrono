# Acceptance 1: no user path runs the insights passes the estimate names

What the user did: on the built flask copy, set an `insights` model (opus),
turned `insights` on at threshold 50 000. The dry run and the settings line
said "Would review 2 topics": topic 17 and the root 19. Pressed Sync now
(nothing changed in the source), then ran `settle` (Runs > "13. settle", or
`POST /jobs {"op":"settle"}`).

What happened: the sync reviewed 17, 18, then 17 again (3 passes), not the
root. `settle` returned `{"settled": false, "held": 0, "released": 0}` and
ran nothing. After 4 syncs the root still has no pass; the dry run still
lists it. The only path left is a full `maintain`/build-tree.

Expected: turning the step on and using the dashboard's actions runs the
passes the estimate states, the root included (goal O2: "settle on the flask
copy gives one pass to each node ... and to the root"); or the settings line
says which action runs them and what a sync will do instead.

Where it comes from: `tree/settle.py` `settle()` returns early unless
`should_settle` (churn or misfit) trips; `force` is not reachable from the
API or the dashboard. The sync chain has no rule for the root
(`docs/summarization.md`: "the root has no rule of its own on a sync"), while
the dry run describes "what the next build would review". The Runs page
describes settle as "place the sections that were still waiting", and the
insights help text does not say when reviews run.

Evidence: `dev/evidence/acceptance-1/ev/settle-report.txt`,
`sync1-report.txt`, `o1-dryrun-thresholds.txt`, `o2-passes.txt`.
