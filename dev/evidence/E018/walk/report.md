# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob. 22 questions x 3 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| levels-2 | 19/22 | 20/22 | 21/22 | 4.0 | 4.1 | 19/19 | 1088400 | 19181 | 11.8 | 1.75 |
| levels-3 | 20/22 | 20/22 | 22/22 | 4.2 | 4.2 | 18/19 | 757643 | 19153 | 11.4 | 1.32 |
| raw | 21/22 | 21/22 | 22/22 | 1.8 | 1.5 | 19/19 | 508501 | 13902 | 9.9 | 0.83 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "The canary word is PELICAN-7731, and the other distinctive names are the `graphify` skill (trigger `/graphify`) and `sensitive-canary` 0.8.2 with its `/update-canary` command. The Plexus context also names `website-monoreact`, `website-backoffice-v3`, `website-myaccount-v3`, `terraform-auth0`, `terr"
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "There are no canary words, skill names or memory-file entries beyond the context message. The only distinctive names in my instructions are the tools: - **Glob** - **Grep** - **Read** The instructions also mention deferred tools, but none are named."
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### levels-2 (export, `/Users/orest/repos/hrono/.claude/worktrees/E018/.scratch/run2/levels-2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 5 | 5 | 1 | 7 | 96174 | 15.6 |
| q02 | shallow | yes | yes | yes | 4 | 4 | 1 | 4 | 36776 | 10.1 |
| q03 | shallow | no | no | yes | 2 | 2 | 1 | 2 | 12536 | 8.4 |
| q04 | deep | no | yes | no | 5 | 5 | 1 | 7 | 66763 | 15.0 |
| q05 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 26557 | 8.8 |
| q06 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 26740 | 10.2 |
| q07 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 26606 | 9.5 |
| q08 | deep | yes | yes | yes | 6 | 6 | 1 | 10 | 133370 | 18.6 |
| q09 | deep | yes | yes | yes | 6 | 6 | 1 | 6 | 94288 | 14.8 |
| q10 | deep | yes | yes | yes | 4 | 4 | 1 | 4 | 40133 | 12.4 |
| q11 | deep | yes | yes | yes | 5 | 4 | 1 | 7 | 62729 | 12.1 |
| q12 | shallow | yes | yes | yes | 4 | 4 | 1 | 4 | 39351 | 9.2 |
| q13 | deep | yes | yes | yes | 4 | 4 | 1 | 4 | 38644 | 9.9 |
| q14 | deep | yes | yes | yes | 4 | 4 | 1 | 5 | 32120 | 10.3 |
| q15 | deep | no | no | yes | 3 | 3 | 1 | 3 | 27637 | 9.7 |
| q16 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 27464 | 8.9 |
| q17 | deep | yes | yes | yes | 9 | 8 | 1 | 10 | 125524 | 22.5 |
| q18 | deep | yes | yes | yes | 3 | 3 | 1 | 5 | 42552 | 12.4 |
| q19 | shallow | yes | yes | yes | 4 | 4 | 1 | 4 | 45983 | 10.1 |
| q20 | none | yes | yes | yes | 2 | - | - | 3 | 16843 | 10.1 |
| q21 | none | yes | yes | yes | 3 | - | - | 4 | 29642 | 11.0 |
| q22 | none | yes | yes | yes | 3 | - | - | 5 | 39968 | 10.5 |

Pages opened, in order:

- q01: root.md > 13/brief.md > 15/brief.md > 15/src-hrono-cli-py-280.md > 14/src-hrono-tree-commands-py-528.md
- q02: root.md > 12/brief.md > 6/brief.md > 12/src-hrono-summarize-pool-py-520.md
- q03: root.md > 15/src-hrono-auth-users-py-279.md
- q04: root.md > 2/brief.md > 2/src-hrono-server-templates-export-html-475.md > 2/src-hrono-export-render-py-359.md > 16/src-hrono-export-collapse-py-357.md
- q05: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-417.md
- q06: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-417.md
- q07: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-417.md
- q08: root.md > 16/brief.md > 14/brief.md > 8/brief.md > 13/src-hrono-tree-update-py-532.md > 13/src-hrono-cluster-placement-py-293.md
- q09: root.md > 16/brief.md > 14/brief.md > 8/brief.md > 13/brief.md > 13/src-hrono-cluster-repair-py-295.md
- q10: root.md > 12/brief.md > 14/brief.md > 12/src-hrono-summarize-propagate-py-521.md
- q11: root.md > 8/brief.md > 5/brief.md > 10/src-hrono-jobs-worker-py-397.md > 10/src-hrono-jobs-worker-py-398.md
- q12: root.md > 11/brief.md > 4/brief.md > 4/glossary-md-270.md
- q13: root.md > 4/brief.md > 3/brief.md > 3/src-hrono-ingest-split-constants-py-379.md
- q14: root.md > 4/brief.md > 4/src-hrono-ingest-git-syncer-py-369.md > 5/src-hrono-registry-validation-git-auth-py-438.md
- q15: root.md > 6/brief.md > 6/src-hrono-llm-claude-code-py-400.md
- q16: root.md > 6/brief.md > 6/src-hrono-llm-claude-code-py-400.md
- q17: root.md > 8/brief.md > 14/brief.md > 14/src-hrono-tree-update-py-533.md > 8/src-hrono-db-migrations-0017-incubator-sql-327.md > 16/brief.md > 5/brief.md > 13/src-hrono-cluster-incubator-py-286.md > 13/src-hrono-cluster-incubator-py-287.md
- q18: root.md > 2/src-hrono-export-render-py-359.md > 16/src-hrono-export-collapse-py-357.md
- q19: root.md > 13/brief.md > 15/brief.md > 15/src-hrono-profile-store-py-411.md
- q20: root.md > 17/src-hrono-server-config-view-py-446.md
- q21: root.md > 5/brief.md > 15/brief.md
- q22: root.md > 18/brief.md > 15/brief.md

### levels-3 (export, `/Users/orest/repos/hrono/.claude/worktrees/E018/.scratch/run2/levels-3`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 4 | 4 | 2 | 7 | 40899 | 13.5 |
| q02 | shallow | yes | yes | yes | 4 | - | - | 4 | 20729 | 9.8 |
| q03 | shallow | no | no | yes | 2 | 2 | 2 | 2 | 9654 | 7.7 |
| q04 | deep | yes | yes | yes | 4 | 4 | 2 | 5 | 23251 | 9.8 |
| q05 | deep | yes | yes | yes | 3 | 3 | 2 | 4 | 17213 | 8.4 |
| q06 | deep | yes | yes | yes | 5 | 5 | 2 | 5 | 32894 | 12.1 |
| q07 | deep | yes | yes | yes | 4 | 4 | 2 | 4 | 30228 | 10.9 |
| q08 | deep | yes | yes | yes | 3 | 3 | 2 | 4 | 20392 | 10.0 |
| q09 | deep | yes | yes | yes | 8 | 8 | 2 | 8 | 93821 | 16.9 |
| q10 | deep | yes | yes | yes | 3 | 3 | 2 | 5 | 48577 | 11.9 |
| q11 | deep | yes | yes | yes | 4 | 3 | 2 | 7 | 24189 | 11.0 |
| q12 | shallow | yes | yes | yes | 5 | 5 | 2 | 6 | 59180 | 11.9 |
| q13 | deep | yes | yes | yes | 3 | 3 | 2 | 4 | 27512 | 9.2 |
| q14 | deep | yes | yes | yes | 7 | 6 | 2 | 7 | 53242 | 14.4 |
| q15 | deep | no | no | yes | 5 | 5 | 2 | 5 | 33867 | 12.4 |
| q16 | deep | yes | yes | yes | 5 | 5 | 2 | 5 | 33648 | 11.5 |
| q17 | deep | yes | yes | yes | 4 | 3 | 2 | 5 | 20446 | 10.5 |
| q18 | deep | yes | yes | yes | 5 | 5 | 2 | 6 | 46616 | 13.0 |
| q19 | shallow | yes | yes | yes | 5 | 5 | 2 | 5 | 61129 | 12.2 |
| q20 | none | yes | yes | yes | 3 | - | - | 5 | 15668 | 10.1 |
| q21 | none | yes | yes | yes | 3 | - | - | 5 | 23949 | 13.2 |
| q22 | none | yes | yes | yes | 4 | - | - | 5 | 20539 | 10.6 |

Pages opened, in order:

- q01: root.md > 20/brief.md > 15/src-hrono-cli-py-280.md > 14/src-hrono-tree-commands-py-528.md
- q02: root.md > 20/brief.md > 19/brief.md > 12/brief.md
- q03: root.md > 15/src-hrono-auth-users-py-279.md
- q04: root.md > 20/brief.md > 2/src-hrono-export-render-py-359.md > 16/src-hrono-export-collapse-py-357.md
- q05: root.md > 20/brief.md > 11/src-hrono-recall-fusion-py-417.md
- q06: root.md > 20/brief.md > 19/brief.md > 11/brief.md > 11/src-hrono-recall-fusion-py-417.md
- q07: root.md > 20/brief.md > 11/brief.md > 11/src-hrono-recall-fusion-py-417.md
- q08: root.md > 20/brief.md > 13/src-hrono-cluster-placement-py-293.md
- q09: root.md > 19/brief.md > 20/brief.md > 14/brief.md > 8/brief.md > 13/brief.md > 16/brief.md > 13/src-hrono-cluster-repair-py-295.md
- q10: root.md > 20/brief.md > 12/src-hrono-summarize-propagate-py-521.md
- q11: root.md > 19/brief.md > 10/src-hrono-jobs-worker-py-397.md > 10/src-hrono-jobs-worker-py-398.md
- q12: root.md > 20/brief.md > 11/brief.md > 4/brief.md > 4/glossary-md-270.md
- q13: root.md > 20/brief.md > 3/src-hrono-ingest-split-constants-py-379.md
- q14: root.md > 20/brief.md > 19/brief.md > 5/brief.md > 4/brief.md > 5/src-hrono-registry-validation-git-auth-py-438.md > 4/src-hrono-ingest-git-syncer-py-369.md
- q15: root.md > 19/brief.md > 20/brief.md > 6/brief.md > 6/src-hrono-llm-claude-code-py-400.md
- q16: root.md > 20/brief.md > 19/brief.md > 6/brief.md > 6/src-hrono-llm-claude-code-py-400.md
- q17: root.md > 20/brief.md > 13/src-hrono-cluster-incubator-py-286.md > 13/src-hrono-cluster-incubator-py-287.md
- q18: root.md > 19/brief.md > 20/brief.md > 2/brief.md > 16/src-hrono-export-collapse-py-357.md
- q19: root.md > 20/brief.md > 13/brief.md > 15/brief.md > 15/src-hrono-profile-store-py-411.md
- q20: root.md > 20/brief.md > 19/brief.md
- q21: root.md > 20/brief.md > 15/readme-md-271.md
- q22: root.md > 20/brief.md > 19/brief.md > 11/brief.md

### raw (raw, `/Users/orest/repos/hrono/.claude/worktrees/E018/.scratch/run2/raw`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 3 | 7 | 31987 | 12.2 |
| q02 | shallow | yes | yes | yes | 2 | 1 | 3 | 4 | 18012 | 8.5 |
| q03 | shallow | yes | yes | yes | 2 | 1 | 3 | 3 | 12006 | 8.6 |
| q04 | deep | yes | yes | yes | 2 | 2 | 3 | 6 | 32536 | 10.1 |
| q05 | deep | yes | yes | yes | 1 | 1 | 3 | 5 | 18349 | 9.3 |
| q06 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 15503 | 8.4 |
| q07 | deep | yes | yes | yes | 3 | 2 | 3 | 8 | 42046 | 15.6 |
| q08 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 13402 | 7.4 |
| q09 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 15077 | 7.2 |
| q10 | deep | yes | yes | yes | 2 | 1 | 3 | 3 | 15630 | 9.5 |
| q11 | deep | yes | yes | yes | 2 | 2 | 3 | 6 | 36854 | 12.3 |
| q12 | shallow | yes | yes | yes | 1 | 1 | 4 | 3 | 11354 | 7.0 |
| q13 | deep | yes | yes | yes | 1 | 1 | 4 | 2 | 11235 | 6.2 |
| q14 | deep | yes | yes | yes | 3 | 3 | 4 | 5 | 24951 | 10.9 |
| q15 | deep | no | no | yes | 1 | 1 | 3 | 3 | 10339 | 8.3 |
| q16 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 10183 | 7.1 |
| q17 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 14581 | 7.5 |
| q18 | deep | yes | yes | yes | 1 | 1 | 3 | 4 | 17525 | 7.8 |
| q19 | shallow | yes | yes | yes | 5 | 5 | 3 | 14 | 72793 | 20.8 |
| q20 | none | yes | yes | yes | 3 | - | - | 6 | 28149 | 11.4 |
| q21 | none | yes | yes | yes | 1 | - | - | 6 | 26710 | 11.0 |
| q22 | none | yes | yes | yes | 2 | - | - | 6 | 29279 | 11.2 |

Pages opened, in order:

- q01: hrono/cli.py > tree/commands.py
- q02: summarize/pool.py > README.md
- q03: crypto/tokens.py > auth/users.py
- q04: ui/export.py > export/collapse.py
- q05: recall/fusion.py
- q06: recall/fusion.py
- q07: GLOSSARY.md > recall/fusion.py > recall/engine.py
- q08: cluster/placement.py
- q09: cluster/repair.py
- q10: summarize/propagate.py > summarize/faithfulness.py
- q11: server/jobs.py > jobs/worker.py
- q12: split/constants.py
- q13: split/constants.py
- q14: ingest/git_syncer.py > ingest/git_reader.py > validation/git_auth.py
- q15: llm/claude_code.py
- q16: llm/claude_code.py
- q17: cluster/incubator.py
- q18: export/collapse.py
- q19: hrono/paths.py > README.md > hrono/cli_boundary.py > client/__init__.py > profile/store.py
- q20: README.md > pyproject.toml > CONTRIBUTING.md
- q21: README.md
- q22: GLOSSARY.md > README.md

## Failed paths

### levels-2 / q03: How does hrono store a user's API token in the database?

- expected: sha-256, sha256 in src/hrono/crypto/tokens.py, src/hrono/auth/users.py
- answered: Only a one-way hash of the token (`hash_token(token)`) is saved, in the `token_hash` column of the `users` table. The raw token is returned once at creation and never stored.
- cited: src/hrono/auth/users.py
- tools in order: Read > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-is-a-hierarchical-incrementally-updated-knowledge-base-15/src-hrono-auth-users-py-279.md` (src/hrono/auth/users.py)

### levels-2 / q04: In the export, how many entries is one index page budgeted to list?

- expected: 40 in src/hrono/export/collapse.py
- answered: One index page is budgeted to list 40 entries (`WIDTH = 40`), which is about 10 KB, the size of one section.
- cited: hrono-topic-tree-system-a-stored-hierarchy-of-topics-and-sec-16/src-hrono-export-collapse-py-357.md (repository path: src/hrono/export/collapse.py)
- tools in order: Read > Read > Read > Read > Glob > Glob > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-codebase-2/brief.md`
  3. `hrono-codebase-2/src-hrono-server-templates-export-html-475.md` (src/hrono/server/templates/export.html)
  4. `hrono-codebase-2/src-hrono-export-render-py-359.md` (src/hrono/export/render.py)
  5. `hrono-topic-tree-system-a-stored-hierarchy-of-topics-and-sec-16/src-hrono-export-collapse-py-357.md` (src/hrono/export/collapse.py)

### levels-2 / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs the CLI from `paths.cli_workdir`, an empty directory that hrono owns, because the CLI reads the project memory of its working directory and this keeps that out of the call. `--safe-mode` also covers this, and the empty directory is the second lock.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `model-call-layer-of-the-hrono-project-m4-summarizers-and-emb-6/brief.md`
  3. `model-call-layer-of-the-hrono-project-m4-summarizers-and-emb-6/src-hrono-llm-claude-code-py-400.md` (src/hrono/llm/claude_code.py)

### levels-3 / q03: How does hrono store a user's API token in the database?

- expected: sha-256, sha256 in src/hrono/crypto/tokens.py, src/hrono/auth/users.py
- answered: Only a one-way hash of the token (`hash_token(token)`) is stored, in the `users.token_hash` column. The raw token is returned once at creation and never persisted.
- cited: src/hrono/auth/users.py
- tools in order: Read > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-parent-brief-20/hrono-is-a-hierarchical-incrementally-updated-knowledge-base-15/src-hrono-auth-users-py-279.md` (src/hrono/auth/users.py)

### levels-3 / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs the CLI from `paths.cli_workdir`, an empty directory that hrono owns. The CLI reads the project memory of its working directory, so an empty directory stops that context from leaking in, and it backs up `--safe-mode`.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Read > Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-is-a-python-sqlite-knowledge-tree-system-with-a-fastap-19/brief.md`
  3. `hrono-parent-brief-20/brief.md`
  4. `hrono-parent-brief-20/model-call-layer-of-the-hrono-project-m4-summarizers-and-emb-6/brief.md`
  5. `hrono-parent-brief-20/model-call-layer-of-the-hrono-project-m4-summarizers-and-emb-6/src-hrono-llm-claude-code-py-400.md` (src/hrono/llm/claude_code.py)

### raw / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs from `paths.cli_workdir`, an empty directory hrono owns, created if missing and passed as `cwd` to the subprocess. This stops the CLI from reading the PROJECT MEMORY of whatever directory it was launched in, which acts as a second safeguard alongside `--safe-mode`.
- cited: src/hrono/llm/claude_code.py
- tools in order: Glob > Glob > Read
- pages opened in order:
  1. `src/hrono/llm/claude_code.py` (src/hrono/llm/claude_code.py)
