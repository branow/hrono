# Acceptance 1: first syncs after the upgrade rewrite and reshape an unchanged tree

What the user did: served the flask copy (built 2026-10-10, Home: "up to
date") on current main, pressed Sync now with nothing changed in the source,
then synced again.

What happened: sync 1 rewrote all 16 leaf briefs (the stored `brief` prompt
hash changed, 9b5eac5f to 1c7c143a), split 4 topics, refiled 64 sections and
rewrote 21 briefs: 54 calls. Sync 2 (still no change) migrated 6 sections and
rewrote 5 briefs (8 calls, misfit above baseline). Sync 3 was quiet. Nothing
warned the admin before or said why, and these rewrites are what started the
insights passes.

Expected: an unchanged source costs nothing ("settled knowledge does not
move"). A one-time re-brief or reshape after an upgrade is announced first
(Home or Health: what will be rewritten, and the cost), not discovered on
Usage.

Where it comes from (likely): the default prompt edits in this run mark every
brief stale. Embedding the old condensations (`embed/op.py`, E056) moves the
members onto condensation vectors, and monitor/repair then reshape.

Evidence: `dev/evidence/acceptance-1/ev/sync1-report.txt`,
`sync2-report.txt`, `sync5-report.txt`, `usage-by-run.txt`.
