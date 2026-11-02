# Acceptance 1: changing a git source's url is ignored by sync

What the user did: `hrono sources set flask` with a new `url` (a clone of
the same repository carrying one new commit). The dry run said "this source
decides what gets pulled, so the next sync may change its sections". Then ran
`hrono tree sync flask`.

What happened: the sync reported `"changed": false`. The source cache under
`.hrono/cache/sources/flask` still has `origin` set to the old url, so `git
fetch origin` read the old remote and the new commit never arrived. The run
said nothing about it.

Expected: the next sync fetches from the url the registry holds, or the save
says the cache must be reset.

Where it comes from: `ingest/git_syncer.py` `git_sync` runs `fetch origin`
on an existing cache without updating the remote to `config["url"]`.
Outside this run's goal; found on the way to O3 (worked around by setting the
cache's remote by hand).

Evidence: `dev/evidence/acceptance-1/ev/sync3-report.txt` (no change) vs
`sync4-report.txt` (after the remote was fixed by hand).
