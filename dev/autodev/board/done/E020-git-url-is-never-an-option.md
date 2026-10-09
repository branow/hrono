---
id: E020
title: a git source URL can never reach git as an option
priority: medium
depends_on: []
requirements: []
---

## Goal
A source URL starting with "-" (e.g. `--upload-pack=<cmd>`) is passed to
`git ls-remote` / `git clone` positionally and read as an option. Admin-only to
register, but E005's home runs `ls-remote` for every reader. Close it twice.

## Tickets

### 1 reject a leading "-", and end options before every URL
Change: `GitSource.url` rejects a value starting with "-" (actionable 4xx);
every git call that takes a URL puts `--` before it.
Done when:
- [ ] registering `--upload-pack=touch /tmp/x` is a 400/422 naming the field;
  nothing stored, nothing run
- [ ] each git URL call has `--` before the URL, pinned by a test that fails
  without it (real git, real `ls-remote`/`clone` of a local repo still works)
- [ ] if E005 has merged, `ingest/remote_head.py` is covered too
Look at: registry/collections/sources.py, registry/validation/git_validation.py,
ingest/git_syncer.py, ingest/remote_head.py (E005)

## Out of scope
- other source types' URLs (HTTP clients, not argv)

## Log
- 2026-10-03 po: created from backlog git-url-leading-dash (qa E005 r1).
- 2026-10-03 dev r1: ticket 1 0619ee1; 422 via API test, real clone of local repo, argv pin for ls-remote (git refuses a dash path there); mutated each of the 3 guards, each test failed. remote_head.py not on main (E005 unmerged), so it needs the same -- when E005 lands.
- 2026-10-03 qa r1: FAIL at 0619ee1. E005 is merged (dcd7bc7) so main's ingest/remote_head.py:32 still runs `ls-remote url HEAD` with no `--`: rebase on main and cover it (Done-when 3). Also: ls-remote test spies subprocess.run (monkeypatch); a real-git test of the payload works. Drove POST/PUT /sources (422 naming url, nothing stored), real sync job of a local repo through serve; re-ran all 3 guard mutations plus 2 of mine, all killed.
- round 2: rebased onto main, remote_head ls-remote gets --, spy replaced by real-git marker tests; mutated both ls-remote -- (killed).
- 2026-10-03 qa r2: PASS at da1a1bc (rebased on main ebad3d8). r1 findings closed: remote_head ls-remote has --, subprocess spy replaced by real-git marker tests. Ruff clean, 253 affected tests pass (all <0.5s). Drove serve on scratch db: POST/PUT dash URLs 422 loc [git,url], nothing stored, no marker; local repo 201; remote_head of it matches rev-parse. Mutations killed: drop -- in remote_head (marker created), validate_git, clone; startswith('--'); remove url validator.
- 2026-10-03 po: ACCEPT at da1a1bc. All 3 Done-when met per qa r2; every URL-taking git call (validate ls-remote, remote_head ls-remote, clone) ends options; fetch uses origin. No user doc change needed.
- merged to main at 39e15c3
