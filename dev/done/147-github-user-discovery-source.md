---
id: 147
title: a github-user source discovers an owner's repos and ingests them all
priority: high
size: medium
depends_on: [141, 142, 143]
spec_refs: [build-order.md#T41.2, implementation-notes.md]
---

## Context
M8's first real reader, and the proof that #141-#143 bought what they claimed:
a source type that is not a single git url should now be a model variant plus
two table entries, with no engine edit anywhere. `github-user` is the one M8
type that can be verified against a REAL provider here — GitHub's user-repos
endpoint answers unauthenticated — so it is the honest place to start.

The spec settles the shape (`implementation-notes.md`): a discovery source
"enumerates many repos via provider API. Each discovered repo still gets a
`git://<host>/<owner>/<repo>` identity; discovery is only how repos are found,
never their address. Full re-discovery on each sync (v1)."

## Design, decided (do not re-litigate)
- ONE source row, many repos. Not children: the registry stores what the user
  declared, and a source that silently spawns four more rows is a surprise the
  user then has to manage.
- A discovered repo's units keep their own COMMIT as their version, so a repo
  that did not change is not re-ingested because a sibling did. `Unit` gains an
  optional `version` override for exactly this; everything else about the
  contract stands.
- Identity comes out right without an instance override: `instance` is
  `github.com/<owner>` and a unit's path is `<repo>/<file path>`, which renders
  `git://github.com/<owner>/<repo>/<file>@<sha>` — the spec's address, and a
  path that stays unique within the source (two repos may both hold
  `README.md`, and the diff keys by path).
- The SOURCE version (`source_state`) is a digest over the sorted
  repo -> commit map: one opaque string that changes when any repo moved.

## Description
- `GithubUserSource` model variant: `name`, `type: "github-user"`, `owner`,
  `auth` (reuse `GitAuth`), optional `include` / `exclude` repo-name globs.
- A validator entry: the owner resolves at the API (and the token authenticates
  if one is given). Injected fetch seam, like `validate_git`'s `run`.
- A syncer entry: enumerate, filter by the globs, clone or pull each repo into
  `cache/<source>/<repo>`, return the digest version. Reuses the git syncer per
  repo rather than reimplementing clone/pull.
- A reader entry: units from every clone, path prefixed with the repo name,
  version = that repo's HEAD. Reuses the git reader per repo, including its
  filter rules.
- Pagination: GitHub pages at 30 by default; follow pages until short.

## Acceptance criteria
- [x] Registering a `github-user` source validates the owner and stores it
      with its token encrypted.
- [x] `sync` clones every matching repo and pins one version for the source;
      re-running it pulls rather than re-cloning.
- [x] `split` stores sections for every repo, each addressed
      `git://github.com/<owner>/<repo>/<path>@<that repo's sha>`.
- [x] Repo-name `include`/`exclude` globs are honoured.
- [x] Enumeration is driven in a test through a REAL HTTP round trip (a local
      stub server, not a mocked client object) — #108.
- [x] Verified by hand against the real api.github.com during qa, with the
      evidence in the review log.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- `bitbucket-workspace` (T41.1) — its own ticket, one more table entry.
- Rate-limit handling beyond a clear error, and conditional requests.
- Per-repo filter overrides.

## Review log
- 2026-09-23 po: authored. First M8 reader; the design decisions above are
  settled so dev does not stop to ask.

- 2026-09-23 dev: `ingest/github.py` holds the only new logic — enumeration
  (paged, stopping on a short page), the repo-name globs, and the repo -> HEAD
  map the sync writes into the cache. Everything below that is the git type's:
  `git_sync` clones and pulls each repo, `git_reader.git_units` applies the
  same filter rules to each working tree.

  Two contract additions, both forced by the spec's rule that discovery is
  never an address:
  - `Unit.version` (optional): each repo's files carry that repo's commit, so a
    repo that did not move is not re-ingested because a sibling did.
  - `Reader.addresses_as` (optional): a `github-user` unit is addressed
    `git://...`, because it IS git content — found through the API, not owned
    by it.

  Restructured while here: the Unit/Reader CONTRACT moved to
  `hrono/ingest/__init__.py` (which imports nothing but the error base), the
  git reader got its own module, and `readers.py` is now just the table — the
  same one-way shape `syncers.py` has. `SplitError` joined `SyncError` at the
  package root for the same reason.

  The heads map is read from the cache, never re-derived with `git rev-parse`:
  the reader must describe the bytes the SYNC left, and a repo pulled by
  something else in between would otherwise be addressed at a commit whose
  content was never ingested.

  Mutations run: pagination stopping after one page -> 1 fails; include globs
  ignored -> 1; every unit taking the source version -> 2; discovery becoming
  the address -> 1; a 404 owner treated as an empty list -> 1.

  ONE MUTATION SURVIVED AND WAS FIXED, not explained away: mutating the address
  rule in `update.py` changed nothing, because my update test computed the
  address type itself instead of driving the code (#128's trap, in my own
  test). The real defect it exposed was worse than the test gap — the rule
  lived in TWO places, so a full split and an incremental update could address
  the same unit differently and every unit would look changed on the next diff.
  Both now call one `readers.resolve(config)`, and mutating it fails 1 test.

- 2026-09-23 qa: PASSED, and this is the strongest evidence yet that #141-#143
  bought what they promised: `github-user` shipped as a model variant plus
  three table entries, and `git diff` touches no ingest engine except the two
  lines that read the new contract fields.

  DRIVEN LIVE AGAINST REAL GITHUB (the ticket's own criterion), server on 8139:
  - `POST /sources` with `owner: octocat`, `include: [Hello-World, Spoon-Knife]`
    -> 201, token field masked.
  - `POST /sources` with a nonexistent owner -> 400 "no such github owner".
  - `POST /jobs` op=sync -> succeeded; both repos cloned into
    `cache/sources/octo/<repo>`.
  - `POST /jobs` op=split -> succeeded, and the sections are:
      git | Hello-World/README      | git://github.com/octocat/Hello-World/README@7fd1a60b...
      git | Spoon-Knife/README.md   | git://github.com/octocat/Spoon-Knife/README.md@d0dd1f61...
      git | Spoon-Knife/index.html  | git://github.com/octocat/Spoon-Knife/index.html@d0dd1f61...
      git | Spoon-Knife/styles.css  | git://github.com/octocat/Spoon-Knife/styles.css@d0dd1f61...
    Two repos, two different real upstream commits, one source row, every unit
    addressed as git. That is the spec's rule, observed rather than asserted.
  - the source's own version is a digest, distinct from either commit.

  Re-ran two dev mutations (include globs ignored; every unit taking the source
  version) and added one dev did not: `resolve` returning the source name as
  the instance -> 2 fail. Enumeration is driven over a real socket, not a
  mocked client (#108). Gate clean, 1003 passing, commit atomic and
  subject-only.

  Credit where due: dev found a surviving mutation in their own test and fixed
  the DESIGN it exposed rather than the assertion. That is the behaviour #128
  was written for.

- 2026-09-23 po: CLOSED. M8 has its first reader, and the seam is now proven by
  a second type rather than by argument. Two things I want on the record:

  1. The address rule ("discovery is how a repo was found, never its address")
     is the reason a repo can move between a `git` source and a `github-user`
     source without re-ingesting a byte. That property is worth more than the
     feature itself and should survive every later reader.
  2. `bitbucket-workspace` (T41.1) is now genuinely one more table entry plus a
     model variant. It stays unauthored until someone has a workspace to point
     it at — the board does not carry work nobody can verify.
