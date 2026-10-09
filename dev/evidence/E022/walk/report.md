# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob. 22 questions x 3 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| before-2 | 19/22 | 20/22 | 20/22 | 3.7 | 3.9 | 18/19 | 1007079 | 17468 | 11.3 | 1.63 |
| after-2 | 18/22 | 19/22 | 21/22 | 3.0 | 2.9 | 18/19 | 799178 | 14614 | 9.5 | 1.42 |
| raw | 22/22 | 22/22 | 22/22 | 1.5 | 1.3 | 19/19 | 410154 | 12360 | 8.9 | 0.73 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "The canary word is **PELICAN-7731**, from the project CLAUDE.md. - **Skill:** `graphify` (trigger `/graphify`), from the global CLAUDE.md. - **Hook output:** `sensitive-canary` (0.8.2 available, vendored 0.8.1) and `/update-canary`, plus a Slack-style output-style instruction. - **Plexus context:** "
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "There's no canary word, skill name, or memory file in my context. The distinctive names I can see are: - **Tools:** Glob, Grep, Read. Their definitions are in my instructions. I'm also told that some deferred tools exist, but none are named. - **Context key:** `userEmail`, which holds the user's ema"
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### before-2 (export, `/Users/orest/repos/hrono/.claude/worktrees/E022/.scratch/out/before-2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | no | yes | no | 3 | 3 | 1 | 4 | 29783 | 10.2 |
| q02 | shallow | yes | yes | yes | 4 | 4 | 1 | 5 | 49355 | 11.7 |
| q03 | shallow | no | no | no | 4 | - | - | 5 | 55534 | 13.2 |
| q04 | deep | yes | yes | yes | 9 | 9 | 1 | 10 | 176758 | 21.1 |
| q05 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 26852 | 8.7 |
| q06 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 27040 | 10.3 |
| q07 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 26873 | 9.6 |
| q08 | deep | yes | yes | yes | 4 | 4 | 1 | 4 | 45258 | 11.4 |
| q09 | deep | yes | yes | yes | 4 | 4 | 1 | 4 | 54405 | 11.3 |
| q10 | deep | yes | yes | yes | 4 | 4 | 1 | 4 | 41756 | 10.6 |
| q11 | deep | yes | yes | yes | 4 | 3 | 1 | 4 | 35812 | 9.6 |
| q12 | shallow | yes | yes | yes | 4 | 4 | 1 | 5 | 38630 | 11.6 |
| q13 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 29405 | 8.7 |
| q14 | deep | yes | yes | yes | 4 | 4 | 1 | 6 | 55157 | 13.8 |
| q15 | deep | no | no | yes | 3 | 3 | 1 | 3 | 27977 | 9.6 |
| q16 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 27844 | 8.8 |
| q17 | deep | yes | yes | yes | 4 | 4 | 1 | 5 | 63169 | 12.6 |
| q18 | deep | yes | yes | yes | 5 | 5 | 1 | 7 | 70366 | 13.5 |
| q19 | shallow | yes | yes | yes | 4 | 4 | 1 | 5 | 58089 | 13.8 |
| q20 | none | yes | yes | yes | 3 | - | - | 3 | 22553 | 8.6 |
| q21 | none | yes | yes | yes | 2 | - | - | 5 | 29073 | 12.8 |
| q22 | none | yes | yes | yes | 2 | - | - | 2 | 15390 | 7.2 |

Pages opened, in order:

- q01: root.md > 14/brief.md > 14/src-hrono-tree-commands-py-260.md
- q02: root.md > 6/brief.md > 12/brief.md > 12/src-hrono-summarize-pool-py-252.md
- q03: root.md > 10/brief.md > 9/src-hrono-db-migrations-0002-users-sql-44.md > 9/brief.md
- q04: root.md > 2/brief.md > 2/src-hrono-server-templates-export-html-207.md > 2/src-hrono-server-templates-guide-html-210.md > 2/src-hrono-export-render-py-91.md > 14/brief.md > 14/src-hrono-export-init-py-88.md > 16/brief.md > 16/src-hrono-export-collapse-py-89.md
- q05: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-149.md
- q06: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-149.md
- q07: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-149.md
- q08: root.md > 14/brief.md > 13/brief.md > 13/src-hrono-cluster-placement-py-25.md
- q09: root.md > 14/brief.md > 13/brief.md > 13/src-hrono-cluster-repair-py-27.md
- q10: root.md > 14/brief.md > 12/brief.md > 12/src-hrono-summarize-propagate-py-253.md
- q11: root.md > 10/brief.md > 10/src-hrono-jobs-worker-py-130.md > 10/src-hrono-jobs-worker-py-129.md
- q12: root.md > 11/brief.md > 11/src-hrono-recall-init-py-144.md > 4/glossary-md-2.md
- q13: root.md > 4/brief.md > 4/glossary-md-2.md
- q14: root.md > 4/brief.md > 4/src-hrono-ingest-git-syncer-py-101.md > 5/src-hrono-registry-validation-git-auth-py-170.md
- q15: root.md > 6/brief.md > 6/src-hrono-llm-claude-code-py-132.md
- q16: root.md > 6/brief.md > 6/src-hrono-llm-claude-code-py-132.md
- q17: root.md > 14/brief.md > 13/brief.md > 13/src-hrono-cluster-incubator-py-18.md
- q18: root.md > 14/brief.md > 2/brief.md > 14/src-hrono-export-init-py-88.md > 16/src-hrono-export-collapse-py-89.md
- q19: root.md > 15/brief.md > 3/brief.md > 15/src-hrono-profile-store-py-143.md
- q20: root.md > 15/brief.md > 3/brief.md
- q21: root.md > 15/readme-md-3.md
- q22: root.md > 11/brief.md

### after-2 (export, `/Users/orest/repos/hrono/.claude/worktrees/E022/.scratch/out/after-2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 3 | 3 | 1 | 3 | 37142 | 9.5 |
| q02 | shallow | yes | yes | yes | 4 | - | - | 4 | 46161 | 9.7 |
| q03 | shallow | no | no | yes | 5 | 5 | 1 | 6 | 49059 | 16.5 |
| q04 | deep | yes | yes | yes | 4 | 4 | 1 | 4 | 37336 | 9.9 |
| q05 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 36228 | 8.3 |
| q06 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 36424 | 9.8 |
| q07 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 36263 | 9.2 |
| q08 | deep | no | yes | no | 2 | 2 | 1 | 4 | 44310 | 10.1 |
| q09 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 44949 | 9.2 |
| q10 | deep | no | no | yes | 3 | 3 | 1 | 4 | 39111 | 9.9 |
| q11 | deep | yes | yes | yes | 4 | 3 | 1 | 4 | 45189 | 9.4 |
| q12 | shallow | yes | yes | yes | 2 | 2 | 1 | 2 | 18561 | 7.8 |
| q13 | deep | yes | yes | yes | 3 | 3 | 1 | 5 | 36322 | 10.5 |
| q14 | deep | yes | yes | yes | 4 | 4 | 1 | 6 | 73067 | 14.2 |
| q15 | deep | no | no | yes | 2 | 2 | 1 | 2 | 20711 | 7.9 |
| q16 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 20576 | 6.8 |
| q17 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 45705 | 10.7 |
| q18 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 21143 | 7.2 |
| q19 | shallow | yes | yes | yes | 4 | 3 | 1 | 4 | 41309 | 10.3 |
| q20 | none | yes | yes | yes | 2 | - | - | 2 | 19038 | 7.1 |
| q21 | none | yes | yes | yes | 2 | - | - | 3 | 28908 | 9.0 |
| q22 | none | yes | yes | yes | 2 | - | - | 2 | 21666 | 7.0 |

Pages opened, in order:

- q01: root.md > 14/brief.md > 14/src-hrono-tree-commands-py-260.md
- q02: root.md > 6/brief.md > 12/brief.md > 15/brief.md
- q03: root.md > 9/src-hrono-db-migrations-0002-users-sql-44.md > 9/src-hrono-db-migrations-0001-keys-sql-43.md > 18/src-hrono-server-auth-py-177.md > 15/src-hrono-auth-users-py-11.md
- q04: root.md > 2/src-hrono-export-render-py-91.md > 14/src-hrono-export-init-py-88.md > 16/src-hrono-export-collapse-py-89.md
- q05: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-149.md
- q06: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-149.md
- q07: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-149.md
- q08: root.md > 13/src-hrono-cluster-placement-py-25.md
- q09: root.md > 13/brief.md > 13/src-hrono-cluster-repair-py-27.md
- q10: root.md > 14/brief.md > 12/src-hrono-summarize-propagate-py-253.md
- q11: root.md > 10/brief.md > 10/src-hrono-jobs-worker-py-130.md > 10/src-hrono-jobs-worker-py-129.md
- q12: root.md > 4/glossary-md-2.md
- q13: root.md > 3/src-hrono-ingest-split-init-py-109.md > 3/src-hrono-ingest-split-constants-py-111.md
- q14: root.md > 4/brief.md > 4/src-hrono-ingest-git-syncer-py-101.md > 5/src-hrono-registry-validation-git-auth-py-170.md
- q15: root.md > 6/src-hrono-llm-claude-code-py-132.md
- q16: root.md > 6/src-hrono-llm-claude-code-py-132.md
- q17: root.md > 13/brief.md > 13/src-hrono-cluster-incubator-py-18.md
- q18: root.md > 16/src-hrono-export-collapse-py-89.md
- q19: root.md > 15/brief.md > 15/src-hrono-profile-store-py-143.md > 15/src-hrono-paths-py-140.md
- q20: root.md > 15/readme-md-3.md
- q21: root.md > 15/readme-md-3.md
- q22: root.md > 11/brief.md

### raw (raw, `/Users/orest/repos/hrono/.claude/worktrees/E022/.scratch/out/raw`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 1 | 1 | 3 | 2 | 12462 | 6.5 |
| q02 | shallow | yes | yes | yes | 2 | 1 | 0 | 4 | 16717 | 9.0 |
| q03 | shallow | yes | yes | yes | 2 | 1 | 3 | 3 | 12029 | 9.6 |
| q04 | deep | yes | yes | yes | 2 | 2 | 3 | 4 | 28110 | 9.4 |
| q05 | deep | yes | yes | yes | 1 | 1 | 3 | 4 | 15630 | 7.9 |
| q06 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 15523 | 8.4 |
| q07 | deep | yes | yes | yes | 1 | 1 | 3 | 5 | 19675 | 9.7 |
| q08 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 13195 | 6.9 |
| q09 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 15077 | 6.3 |
| q10 | deep | yes | yes | yes | 2 | 1 | 3 | 3 | 15506 | 9.1 |
| q11 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 18083 | 8.8 |
| q12 | shallow | yes | yes | yes | 2 | 1 | 4 | 3 | 12941 | 6.7 |
| q13 | deep | yes | yes | yes | 1 | 1 | 4 | 2 | 11262 | 6.3 |
| q14 | deep | yes | yes | yes | 2 | 2 | 4 | 4 | 22189 | 10.2 |
| q15 | deep | yes | yes | yes | 2 | 1 | 3 | 5 | 24354 | 11.4 |
| q16 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 10101 | 6.4 |
| q17 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 14649 | 8.4 |
| q18 | deep | yes | yes | yes | 1 | 1 | 3 | 4 | 17501 | 7.9 |
| q19 | shallow | yes | yes | yes | 4 | 4 | 3 | 10 | 54423 | 16.8 |
| q20 | none | yes | yes | yes | 2 | - | - | 5 | 19421 | 8.5 |
| q21 | none | yes | yes | yes | 1 | - | - | 7 | 22338 | 10.9 |
| q22 | none | yes | yes | yes | 2 | - | - | 6 | 18968 | 9.8 |

Pages opened, in order:

- q01: tree/commands.py
- q02: README.md > summarize/pool.py
- q03: crypto/tokens.py > auth/users.py
- q04: ui/export.py > export/collapse.py
- q05: recall/fusion.py
- q06: recall/fusion.py
- q07: recall/fusion.py
- q08: cluster/placement.py
- q09: cluster/repair.py
- q10: summarize/propagate.py > summarize/faithfulness.py
- q11: jobs/worker.py
- q12: split/constants.py > GLOSSARY.md
- q13: split/constants.py
- q14: ingest/git_syncer.py > validation/git_auth.py
- q15: llm/claude_code.py > hrono/paths.py
- q16: llm/claude_code.py
- q17: cluster/incubator.py
- q18: export/collapse.py
- q19: hrono/paths.py > README.md > hrono/cli.py > profile/store.py
- q20: README.md > pyproject.toml
- q21: README.md
- q22: GLOSSARY.md > pyproject.toml

## Failed paths

### before-2 / q01: What hop limit does `hrono tree export` use when --levels is not given?

- expected: 4 in src/hrono/tree/commands.py
- answered: The default hop limit is 4 (`--levels` defaults to 4).
- cited: hrono-tree-subsystem-14/src-hrono-tree-commands-py-260.md (repository path: src/hrono/tree/commands.py)
- tools in order: Read > Read > Glob > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-tree-subsystem-14/brief.md`
  3. `hrono-tree-subsystem-14/src-hrono-tree-commands-py-260.md` (src/hrono/tree/commands.py)

### before-2 / q03: How does hrono store a user's API token in the database?

- expected: sha-256, sha256 in src/hrono/crypto/tokens.py, src/hrono/auth/users.py
- answered: hrono stores only a hash of the token, in the unique, non-null `token_hash` column of the `users` table, next to `name` (primary key), `role` and `created_at`. A later migration adds `modified_at` to audit token resets. The raw token is not stored.
- cited: src/hrono/db/migrations/0002_users.sql
- tools in order: Read > Read > Glob > Read > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-backend-s-storage-job-execution-and-operator-layers-10/brief.md`
  3. `sqlite-schema-and-migration-history-for-a-document-indexing--9/src-hrono-db-migrations-0002-users-sql-44.md` (src/hrono/db/migrations/0002_users.sql)
  4. `sqlite-schema-and-migration-history-for-a-document-indexing--9/brief.md`

### before-2 / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs from `paths.cli_workdir`, an hrono-owned, empty directory that is created if missing. The CLI reads the project memory of its working directory, so this keeps operator or project context out of the calls. `--safe-mode` does the same, and the empty directory is a second lock.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `llm-and-embedding-call-layer-of-the-hrono-project-m4-summari-6/brief.md`
  3. `llm-and-embedding-call-layer-of-the-hrono-project-m4-summari-6/src-hrono-llm-claude-code-py-132.md` (src/hrono/llm/claude_code.py)

### after-2 / q03: How does hrono store a user's API token in the database?

- expected: sha-256, sha256 in src/hrono/crypto/tokens.py, src/hrono/auth/users.py
- answered: hrono stores only a one-way hash of the token, in the `users.token_hash` column (TEXT NOT NULL UNIQUE). `create_user` and `reset_token` write `hash_token(token)`, the raw token is returned once and never saved, and `authenticate` hashes the presented token and looks it up by that column.
- cited: src/hrono/auth/users.py, src/hrono/db/migrations/0002_users.sql
- tools in order: Read > Read > Read > Read > Glob > Read
- pages opened in order:
  1. `root.md`
  2. `sqlite-schema-and-migration-history-for-a-document-indexing--9/src-hrono-db-migrations-0002-users-sql-44.md` (src/hrono/db/migrations/0002_users.sql)
  3. `sqlite-schema-and-migration-history-for-a-document-indexing--9/src-hrono-db-migrations-0001-keys-sql-43.md` (src/hrono/db/migrations/0001_keys.sql)
  4. `hrono-server-layer-the-code-behind-the-manual-adjustment-ope-18/src-hrono-server-auth-py-177.md` (src/hrono/server/auth.py)
  5. `hrono-is-a-hierarchical-incrementally-updated-knowledge-base-15/src-hrono-auth-users-py-11.md` (src/hrono/auth/users.py)

### after-2 / q08: What similarity threshold (TAU) decides whether a new section is placed into an existing cluster?

- expected: 0.7 in src/hrono/cluster/placement.py
- answered: TAU = 0.70. A new section joins the nearest cluster centroid if its dot-product similarity is >= 0.70, otherwise it is parked in the incubator.
- cited: reference-for-hrono-a-python-project-that-builds-a-topic-tre-13/src-hrono-cluster-placement-py-25.md (repository path: src/hrono/cluster/placement.py)
- tools in order: Read > Glob > Glob > Read
- pages opened in order:
  1. `root.md`
  2. `reference-for-hrono-a-python-project-that-builds-a-topic-tre-13/src-hrono-cluster-placement-py-25.md` (src/hrono/cluster/placement.py)

### after-2 / q10: When a changed leaf is propagated upward, how many judge votes are asked for, and how is the verdict decided?

- expected: majority, median in src/hrono/summarize/propagate.py
- answered: 3 judge votes are asked per changed leaf (BEST_OF = 3), and each unparseable vote is re-asked once, then abstains. The verdict is the middle element of the surviving votes sorted by none < minor < major, and if every vote abstains there is no verdict.
- cited: src/hrono/summarize/propagate.py
- tools in order: Read > Read > Glob > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-tree-subsystem-14/brief.md`
  3. `summarisation-pipeline-of-the-hrono-project-12/src-hrono-summarize-propagate-py-253.md` (src/hrono/summarize/propagate.py)

### after-2 / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs in `paths.cli_workdir`, an empty directory hrono owns, because the Claude Code CLI reads the project memory of its working directory and that must not leak into summarisation calls. `--safe-mode` also covers this, and the empty directory is the second lock.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Read
- pages opened in order:
  1. `root.md`
  2. `llm-and-embedding-call-layer-of-the-hrono-project-m4-summari-6/src-hrono-llm-claude-code-py-132.md` (src/hrono/llm/claude_code.py)
