# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob. 22 questions x 3 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| levels-2 | 19/22 | 20/22 | 21/22 | 3.3 | 3.5 | 19/19 | 1611832 | 16406 | 10.7 | 2.44 |
| levels-3 | 20/22 | 20/22 | 22/22 | 2.3 | 2.2 | 19/19 | 1294629 | 14693 | 9.9 | 2.08 |
| raw | 21/22 | 21/22 | 22/22 | 1.6 | 1.4 | 19/19 | 400704 | 12389 | 9.1 | 0.74 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "The canary word is **PELICAN-7731** (from the project CLAUDE.md), and the skill name is `graphify` (the `/graphify` trigger in your global CLAUDE.md). The session hooks also mention `sensitive-canary` (vendored 0.8.1, 0.8.2 available, update via `/update-canary`) and the `plexus-context` block, whic"
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "There are no canary words or skill names. I did find these distinctive names: - **Tools:** Glob, Grep, Read. A deferred-tool mechanism is also mentioned, but no deferred tool is named. - **Product and model names:** Claude Agent SDK, Claude Code, Sonnet 5.5 (`claude-sonnet-5-5`). - **Context fields:"
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### levels-2 (export, `/Users/orest/repos/hrono/.claude/worktrees/E018/.scratch/run/levels-2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 10 | 10 | 1 | 13 | 328057 | 26.9 |
| q02 | shallow | yes | yes | yes | 4 | 4 | 1 | 4 | 75668 | 9.3 |
| q03 | shallow | no | no | yes | 2 | 2 | 1 | 2 | 32367 | 9.3 |
| q04 | deep | yes | yes | yes | 4 | 4 | 1 | 5 | 62855 | 10.2 |
| q05 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 60553 | 9.1 |
| q06 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 59538 | 10.4 |
| q07 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 59422 | 10.1 |
| q08 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 70084 | 10.0 |
| q09 | deep | yes | yes | yes | 3 | 2 | 1 | 4 | 50979 | 9.6 |
| q10 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 53335 | 11.1 |
| q11 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 31708 | 7.2 |
| q12 | shallow | yes | yes | yes | 3 | 3 | 1 | 4 | 60553 | 9.1 |
| q13 | deep | yes | yes | yes | 4 | 4 | 1 | 4 | 75429 | 10.2 |
| q14 | deep | yes | yes | yes | 4 | 4 | 1 | 5 | 67804 | 11.7 |
| q15 | deep | no | no | yes | 3 | 3 | 1 | 3 | 61412 | 9.5 |
| q16 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 61256 | 8.8 |
| q17 | deep | no | yes | no | 4 | 4 | 1 | 6 | 95448 | 15.2 |
| q18 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 34544 | 7.3 |
| q19 | shallow | yes | yes | yes | 4 | 4 | 1 | 4 | 87978 | 10.7 |
| q20 | none | yes | yes | yes | 1 | - | - | 2 | 30115 | 7.8 |
| q21 | none | yes | yes | yes | 4 | - | - | 7 | 136616 | 15.9 |
| q22 | none | yes | yes | yes | 1 | - | - | 1 | 16111 | 6.0 |

Pages opened, in order:

- q01: root.md > 16/brief.md > 2/brief.md > 13/brief.md > 16/src-hrono-export-collapse-py-357.md > 2/src-hrono-server-templates-export-html-475.md > 15/src-hrono-export-produce-py-358.md > 15/src-hrono-cli-py-280.md > 17/src-hrono-server-ui-export-py-494.md > 14/src-hrono-tree-commands-py-528.md
- q02: root.md > 12/brief.md > 6/brief.md > 12/src-hrono-summarize-pool-py-520.md
- q03: root.md > 15/src-hrono-auth-users-py-279.md
- q04: root.md > 2/brief.md > 2/src-hrono-server-templates-export-html-475.md > 16/src-hrono-export-collapse-py-357.md
- q05: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-417.md
- q06: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-417.md
- q07: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-417.md
- q08: root.md > 13/brief.md > 13/src-hrono-cluster-placement-py-293.md
- q09: root.md > 13/src-hrono-cluster-repair-py-295.md > 13/src-hrono-cluster-repair-py-296.md
- q10: root.md > 12/src-hrono-summarize-briefs-py-516.md > 12/src-hrono-summarize-propagate-py-521.md
- q11: root.md > 10/src-hrono-jobs-worker-py-397.md
- q12: root.md > 11/brief.md > 3/src-hrono-ingest-split-constants-py-379.md
- q13: root.md > 4/brief.md > 3/brief.md > 3/src-hrono-ingest-split-constants-py-379.md
- q14: root.md > 4/src-hrono-ingest-sync-py-387.md > 4/src-hrono-ingest-git-syncer-py-369.md > 5/src-hrono-registry-validation-git-auth-py-438.md
- q15: root.md > 6/brief.md > 6/src-hrono-llm-claude-code-py-400.md
- q16: root.md > 6/brief.md > 6/src-hrono-llm-claude-code-py-400.md
- q17: root.md > 13/src-hrono-tree-update-py-532.md > 14/src-hrono-tree-update-py-533.md > 13/src-hrono-cluster-incubator-py-286.md
- q18: root.md > 16/src-hrono-export-collapse-py-357.md
- q19: root.md > 15/brief.md > 13/brief.md > 15/src-hrono-profile-store-py-411.md
- q20: root.md
- q21: root.md > 2/brief.md > 3/brief.md > 15/readme-md-271.md
- q22: root.md

### levels-3 (export, `/Users/orest/repos/hrono/.claude/worktrees/E018/.scratch/run/levels-3`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 2 | 5 | 76796 | 10.7 |
| q02 | shallow | yes | yes | yes | 3 | 3 | 2 | 6 | 80068 | 11.1 |
| q03 | shallow | no | no | yes | 2 | 2 | 2 | 2 | 38763 | 9.3 |
| q04 | deep | yes | yes | yes | 4 | 4 | 2 | 5 | 85816 | 13.7 |
| q05 | deep | yes | yes | yes | 2 | 2 | 2 | 5 | 57656 | 9.2 |
| q06 | deep | yes | yes | yes | 2 | 2 | 2 | 5 | 57815 | 10.4 |
| q07 | deep | yes | yes | yes | 2 | 2 | 2 | 5 | 57619 | 10.5 |
| q08 | deep | yes | yes | yes | 2 | 2 | 2 | 3 | 58482 | 10.7 |
| q09 | deep | yes | yes | yes | 3 | 2 | 2 | 4 | 60540 | 11.3 |
| q10 | deep | yes | yes | yes | 3 | 3 | 2 | 4 | 63546 | 10.5 |
| q11 | deep | yes | yes | yes | 2 | 2 | 2 | 2 | 38132 | 7.3 |
| q12 | shallow | yes | yes | yes | 2 | 2 | 2 | 4 | 58323 | 9.1 |
| q13 | deep | yes | yes | yes | 2 | 2 | 2 | 4 | 59559 | 9.1 |
| q14 | deep | yes | yes | yes | 3 | 2 | 2 | 5 | 58288 | 10.6 |
| q15 | deep | no | no | yes | 2 | 2 | 2 | 4 | 59590 | 10.0 |
| q16 | deep | yes | yes | yes | 2 | 2 | 2 | 4 | 59418 | 8.9 |
| q17 | deep | yes | yes | yes | 3 | 2 | 2 | 4 | 60887 | 10.6 |
| q18 | deep | yes | yes | yes | 2 | 2 | 2 | 2 | 40972 | 7.6 |
| q19 | shallow | yes | yes | yes | 2 | 2 | 2 | 5 | 57803 | 9.4 |
| q20 | none | yes | yes | yes | 1 | - | - | 2 | 36481 | 7.6 |
| q21 | none | yes | yes | yes | 3 | - | - | 4 | 91349 | 12.3 |
| q22 | none | yes | yes | yes | 1 | - | - | 3 | 36726 | 7.0 |

Pages opened, in order:

- q01: root.md > 14/src-hrono-tree-commands-py-528.md
- q02: root.md > 10/src-hrono-jobs-stages-py-395.md > 12/src-hrono-summarize-pool-py-520.md
- q03: root.md > 15/src-hrono-auth-users-py-279.md
- q04: root.md > 2/src-hrono-export-render-py-359.md > 14/src-hrono-export-init-py-356.md > 16/src-hrono-export-collapse-py-357.md
- q05: root.md > 11/src-hrono-recall-fusion-py-417.md
- q06: root.md > 11/src-hrono-recall-fusion-py-417.md
- q07: root.md > 11/src-hrono-recall-fusion-py-417.md
- q08: root.md > 13/src-hrono-cluster-placement-py-293.md
- q09: root.md > 13/src-hrono-cluster-repair-py-295.md > 13/src-hrono-cluster-repair-py-296.md
- q10: root.md > 12/src-hrono-summarize-briefs-py-516.md > 12/src-hrono-summarize-propagate-py-521.md
- q11: root.md > 10/src-hrono-jobs-worker-py-397.md
- q12: root.md > 3/src-hrono-ingest-split-constants-py-379.md
- q13: root.md > 3/src-hrono-ingest-split-constants-py-379.md
- q14: root.md > 5/src-hrono-registry-validation-git-auth-py-438.md > 4/src-hrono-ingest-git-syncer-py-369.md
- q15: root.md > 6/src-hrono-llm-claude-code-py-400.md
- q16: root.md > 6/src-hrono-llm-claude-code-py-400.md
- q17: root.md > 13/src-hrono-cluster-incubator-py-286.md > 13/src-hrono-cluster-incubator-py-287.md
- q18: root.md > 16/src-hrono-export-collapse-py-357.md
- q19: root.md > 15/src-hrono-profile-store-py-411.md
- q20: root.md
- q21: root.md > 20/brief.md > 15/readme-md-271.md
- q22: root.md

### raw (raw, `/Users/orest/repos/hrono/.claude/worktrees/E018/.scratch/run/raw`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 1 | 1 | 3 | 2 | 12478 | 7.1 |
| q02 | shallow | yes | yes | yes | 2 | 1 | 3 | 3 | 14164 | 7.6 |
| q03 | shallow | yes | yes | yes | 2 | 1 | 3 | 3 | 12120 | 10.2 |
| q04 | deep | yes | yes | yes | 2 | 2 | 3 | 3 | 21943 | 8.4 |
| q05 | deep | yes | yes | yes | 1 | 1 | 3 | 4 | 15721 | 8.2 |
| q06 | deep | yes | yes | yes | 1 | 1 | 3 | 4 | 15807 | 8.9 |
| q07 | deep | yes | yes | yes | 2 | 2 | 3 | 6 | 23085 | 11.6 |
| q08 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 13175 | 6.7 |
| q09 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 15072 | 6.5 |
| q10 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 14471 | 9.7 |
| q11 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 17841 | 7.9 |
| q12 | shallow | yes | yes | yes | 2 | 1 | 4 | 3 | 12943 | 6.8 |
| q13 | deep | yes | yes | yes | 1 | 1 | 4 | 2 | 11266 | 6.3 |
| q14 | deep | yes | yes | yes | 3 | 3 | 4 | 5 | 24991 | 11.2 |
| q15 | deep | no | no | yes | 1 | 1 | 3 | 3 | 10316 | 8.2 |
| q16 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 10160 | 7.2 |
| q17 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 14609 | 7.9 |
| q18 | deep | yes | yes | yes | 2 | 2 | 3 | 3 | 21962 | 8.5 |
| q19 | shallow | yes | yes | yes | 4 | 4 | 3 | 9 | 41120 | 14.8 |
| q20 | none | yes | yes | yes | 2 | - | - | 5 | 17169 | 11.1 |
| q21 | none | yes | yes | yes | 1 | - | - | 7 | 28364 | 12.7 |
| q22 | none | yes | yes | yes | 3 | - | - | 7 | 31927 | 12.7 |

Pages opened, in order:

- q01: tree/commands.py
- q02: summarize/pool.py > README.md
- q03: crypto/tokens.py > auth/users.py
- q04: ui/export.py > export/collapse.py
- q05: recall/fusion.py
- q06: recall/fusion.py
- q07: GLOSSARY.md > recall/fusion.py
- q08: cluster/placement.py
- q09: cluster/repair.py
- q10: summarize/propagate.py
- q11: jobs/worker.py
- q12: split/constants.py > GLOSSARY.md
- q13: split/constants.py
- q14: ingest/git_syncer.py > ingest/git_reader.py > validation/git_auth.py
- q15: llm/claude_code.py
- q16: llm/claude_code.py
- q17: cluster/incubator.py
- q18: ui/export.py > export/collapse.py
- q19: hrono/paths.py > client/http.py > client/__init__.py > profile/store.py
- q20: README.md > pyproject.toml
- q21: README.md
- q22: pyproject.toml > GLOSSARY.md > README.md

## Failed paths

### levels-2 / q03: How does hrono store a user's API token in the database?

- expected: sha-256, sha256 in src/hrono/crypto/tokens.py, src/hrono/auth/users.py
- answered: hrono stores only a one-way hash of the token, in the `users.token_hash` column, via `hash_token(token)`. The raw token is returned once at creation or reset and never stored. Authentication hashes the presented token and matches it against `token_hash`.
- cited: src/hrono/auth/users.py
- tools in order: Read > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-is-a-hierarchical-incrementally-updated-knowledge-base-15/src-hrono-auth-users-py-279.md` (src/hrono/auth/users.py)

### levels-2 / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs from `paths.cli_workdir`, an empty directory hrono owns, because the CLI reads the project memory of its working directory. Using an empty directory keeps that out of the summarizer, as a second lock alongside `--safe-mode`.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `model-call-layer-of-the-hrono-project-m4-summarizers-and-emb-6/brief.md`
  3. `model-call-layer-of-the-hrono-project-m4-summarizers-and-emb-6/src-hrono-llm-claude-code-py-400.md` (src/hrono/llm/claude_code.py)

### levels-2 / q17: How many update runs may a chunk wait in the incubator pool before it is forced out?

- expected: 5, five in src/hrono/cluster/incubator.py
- answered: A chunk may wait at most 5 update runs (`MAX_AGE = 5`). Once it has waited more than 5 runs, it is force-assigned to the nearest existing cluster.
- cited: hrono-a-python-cli-hrono-cli-app-that-builds-and-maintains-a-13/src-hrono-cluster-incubator-py-286.md (repository path: src/hrono/cluster/incubator.py)
- tools in order: Read > Glob > Read > Read > Glob > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-a-python-cli-hrono-cli-app-that-builds-and-maintains-a-13/src-hrono-tree-update-py-532.md` (src/hrono/tree/update.py)
  3. `hrono-a-system-that-builds-a-hierarchical-topic-tree-from-a--14/src-hrono-tree-update-py-533.md` (src/hrono/tree/update.py)
  4. `hrono-a-python-cli-hrono-cli-app-that-builds-and-maintains-a-13/src-hrono-cluster-incubator-py-286.md` (src/hrono/cluster/incubator.py)

### levels-3 / q03: How does hrono store a user's API token in the database?

- expected: sha-256, sha256 in src/hrono/crypto/tokens.py, src/hrono/auth/users.py
- answered: hrono stores only a one-way hash of the token, written by `hash_token(token)` into the `users.token_hash` column. The raw token is returned once at creation or reset, and authentication hashes the presented token and matches it against `token_hash`.
- cited: src/hrono/auth/users.py
- tools in order: Read > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-parent-brief-20/hrono-is-a-hierarchical-incrementally-updated-knowledge-base-15/src-hrono-auth-users-py-279.md` (src/hrono/auth/users.py)

### levels-3 / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs in `paths.cli_workdir`, an empty directory hrono owns, because the CLI reads the PROJECT MEMORY of its working directory and that must not leak into summarization calls. `--safe-mode` already covers this, and the empty directory is a second lock.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Glob > Glob > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-parent-brief-20/model-call-layer-of-the-hrono-project-m4-summarizers-and-emb-6/src-hrono-llm-claude-code-py-400.md` (src/hrono/llm/claude_code.py)

### raw / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs the CLI with `cwd` set to `paths.cli_workdir`, an empty directory hrono owns. The CLI reads the project memory of its working directory, so this keeps the operator's project context out of the call. `--safe-mode` also covers this, and the empty directory is a second lock.
- cited: src/hrono/llm/claude_code.py
- tools in order: Glob > Glob > Read
- pages opened in order:
  1. `src/hrono/llm/claude_code.py` (src/hrono/llm/claude_code.py)
