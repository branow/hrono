# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob,Grep. 22 questions x 3 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| before-2 | 21/22 | 22/22 | 21/22 | 1.2 | 2.0 | 5/19 | 373817 | 12969 | 8.1 | 0.60 |
| after-2 | 21/22 | 21/22 | 22/22 | 1.3 | 1.9 | 7/19 | 544303 | 14543 | 8.7 | 0.88 |
| raw | 22/22 | 22/22 | 22/22 | 0.6 | 1.0 | 11/19 | 379670 | 11938 | 8.2 | 0.46 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "The canary word is PELICAN-7731, and the skill is graphify (`/graphify`, run through the Skill tool). Other names that appear: - **Hook output:** sensitive-canary (0.8.1 vendored, 0.8.2 available) and `/update-canary`. - **Plexus context:** `website-monoreact`, `website-backoffice-v3`, `website-myac"
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "No canary words, skill names or memory-file codes appear in my instructions. The only distinctive names are these: - **Tools:** Glob, Grep, Read. The system prompt also mentions "deferred tools", but none are named. - **Other names:** Claude Agent SDK, Claude Code, and the model name Sonnet 5.5 (`cl"
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### before-2 (export, `/Users/orest/repos/hrono/.claude/worktrees/E022/.scratch/out/before-2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 1 | 3 | 16345 | 7.8 |
| q02 | shallow | yes | yes | yes | 1 | - | - | 3 | 16230 | 8.1 |
| q03 | shallow | yes | yes | yes | 4 | 3 | 1 | 5 | 26565 | 12.1 |
| q04 | deep | yes | yes | yes | 2 | 2 | 1 | 3 | 21937 | 9.5 |
| q05 | deep | yes | yes | yes | 0 | - | - | 3 | 15866 | 9.5 |
| q06 | deep | yes | yes | yes | 2 | 2 | 1 | 3 | 21295 | 8.5 |
| q07 | deep | yes | yes | yes | 1 | - | - | 3 | 16584 | 10.1 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 9501 | 7.3 |
| q09 | deep | yes | yes | yes | 1 | - | - | 3 | 18340 | 8.0 |
| q10 | deep | yes | yes | yes | 1 | - | - | 3 | 23288 | 10.3 |
| q11 | deep | yes | yes | yes | 1 | - | - | 2 | 11158 | 6.0 |
| q12 | shallow | yes | yes | yes | 1 | - | - | 2 | 10065 | 6.4 |
| q13 | deep | yes | yes | yes | 1 | - | - | 3 | 19779 | 8.0 |
| q14 | deep | yes | yes | yes | 1 | 1 | 1 | 2 | 12137 | 7.1 |
| q15 | deep | yes | yes | yes | 1 | - | - | 3 | 15934 | 8.9 |
| q16 | deep | yes | yes | yes | 1 | - | - | 2 | 12081 | 5.8 |
| q17 | deep | no | yes | no | 1 | - | - | 3 | 22265 | 8.7 |
| q18 | deep | yes | yes | yes | 1 | - | - | 3 | 20827 | 8.3 |
| q19 | shallow | yes | yes | yes | 1 | - | - | 2 | 14621 | 7.1 |
| q20 | none | yes | yes | yes | 1 | - | - | 3 | 15079 | 7.8 |
| q21 | none | yes | yes | yes | 1 | - | - | 3 | 14653 | 6.6 |
| q22 | none | yes | yes | yes | 1 | - | - | 3 | 19267 | 7.0 |

Pages opened, in order:

- q01: root.md > 14/src-hrono-tree-commands-py-260.md
- q02: root.md
- q03: root.md > 9/src-hrono-db-migrations-0002-users-sql-44.md > 15/src-hrono-crypto-tokens-py-36.md > 15/src-hrono-auth-users-py-11.md
- q04: root.md > 16/src-hrono-export-collapse-py-89.md
- q05: none
- q06: root.md > 11/src-hrono-recall-fusion-py-149.md
- q07: root.md
- q08: none
- q09: root.md
- q10: root.md
- q11: root.md
- q12: root.md
- q13: root.md
- q14: 5/src-hrono-registry-validation-git-auth-py-170.md
- q15: root.md
- q16: root.md
- q17: root.md
- q18: root.md
- q19: root.md
- q20: root.md
- q21: root.md
- q22: root.md

### after-2 (export, `/Users/orest/repos/hrono/.claude/worktrees/E022/.scratch/out/after-2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 1 | 3 | 22621 | 7.8 |
| q02 | shallow | yes | yes | yes | 1 | - | - | 2 | 12624 | 5.7 |
| q03 | shallow | yes | yes | yes | 3 | 2 | 1 | 4 | 30653 | 10.9 |
| q04 | deep | yes | yes | yes | 1 | - | - | 4 | 32018 | 9.8 |
| q05 | deep | yes | yes | yes | 0 | - | - | 3 | 15603 | 8.3 |
| q06 | deep | yes | yes | yes | 2 | 2 | 1 | 3 | 29292 | 9.2 |
| q07 | deep | yes | yes | yes | 1 | - | - | 3 | 23578 | 8.7 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 9514 | 5.6 |
| q09 | deep | yes | yes | yes | 1 | - | - | 3 | 25731 | 9.1 |
| q10 | deep | yes | yes | yes | 3 | 2 | 1 | 6 | 50933 | 17.0 |
| q11 | deep | yes | yes | yes | 2 | 2 | 1 | 3 | 26248 | 8.2 |
| q12 | shallow | yes | yes | yes | 1 | - | - | 3 | 28217 | 8.8 |
| q13 | deep | yes | yes | yes | 1 | - | - | 3 | 26025 | 8.8 |
| q14 | deep | yes | yes | yes | 1 | 1 | 1 | 2 | 11121 | 7.0 |
| q15 | deep | no | no | yes | 1 | - | - | 3 | 22957 | 9.6 |
| q16 | deep | yes | yes | yes | 1 | - | - | 3 | 24164 | 8.3 |
| q17 | deep | yes | yes | yes | 1 | - | - | 3 | 26547 | 8.6 |
| q18 | deep | yes | yes | yes | 1 | - | - | 3 | 28139 | 8.6 |
| q19 | shallow | yes | yes | yes | 2 | 2 | 1 | 3 | 30560 | 10.2 |
| q20 | none | yes | yes | yes | 1 | - | - | 3 | 20959 | 7.7 |
| q21 | none | yes | yes | yes | 1 | - | - | 3 | 21275 | 7.5 |
| q22 | none | yes | yes | yes | 1 | - | - | 3 | 25524 | 7.0 |

Pages opened, in order:

- q01: root.md > 14/src-hrono-tree-commands-py-260.md
- q02: root.md
- q03: root.md > 15/src-hrono-crypto-tokens-py-36.md > 9/src-hrono-db-migrations-0002-users-sql-44.md
- q04: root.md
- q05: none
- q06: root.md > 11/src-hrono-recall-fusion-py-149.md
- q07: root.md
- q08: none
- q09: root.md
- q10: root.md > 12/src-hrono-summarize-propagate-py-253.md > 12/src-hrono-summarize-propagate-py-253.md
- q11: root.md > 10/src-hrono-jobs-worker-py-129.md
- q12: root.md
- q13: root.md
- q14: 5/src-hrono-registry-validation-git-auth-py-170.md
- q15: root.md
- q16: root.md
- q17: root.md
- q18: root.md
- q19: root.md > 15/src-hrono-profile-store-py-143.md
- q20: root.md
- q21: root.md
- q22: root.md

### raw (raw, `/Users/orest/repos/hrono/.claude/worktrees/E022/.scratch/out/raw`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 1 | 1 | 3 | 3 | 21949 | 9.0 |
| q02 | shallow | yes | yes | yes | 2 | 1 | 3 | 3 | 13487 | 8.0 |
| q03 | shallow | yes | yes | yes | 2 | 1 | 3 | 4 | 19523 | 11.9 |
| q04 | deep | yes | yes | yes | 0 | - | - | 2 | 11343 | 6.8 |
| q05 | deep | yes | yes | yes | 0 | - | - | 2 | 10710 | 6.5 |
| q06 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 13534 | 7.5 |
| q07 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 13217 | 7.6 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 8405 | 5.3 |
| q09 | deep | yes | yes | yes | 0 | - | - | 2 | 15191 | 7.0 |
| q10 | deep | yes | yes | yes | 0 | - | - | 4 | 23167 | 10.5 |
| q11 | deep | yes | yes | yes | 0 | - | - | 2 | 12047 | 6.5 |
| q12 | shallow | yes | yes | yes | 1 | 1 | 4 | 5 | 61166 | 12.8 |
| q13 | deep | yes | yes | yes | 1 | 1 | 4 | 3 | 17935 | 8.2 |
| q14 | deep | yes | yes | yes | 1 | 1 | 4 | 2 | 10746 | 7.0 |
| q15 | deep | yes | yes | yes | 1 | 1 | 2 | 6 | 26571 | 13.7 |
| q16 | deep | yes | yes | yes | 0 | - | - | 2 | 7090 | 5.3 |
| q17 | deep | yes | yes | yes | 0 | - | - | 2 | 14125 | 6.6 |
| q18 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 21619 | 8.2 |
| q19 | shallow | yes | yes | yes | 1 | 1 | 3 | 2 | 12111 | 8.4 |
| q20 | none | yes | yes | yes | 0 | - | - | 3 | 12910 | 7.4 |
| q21 | none | yes | yes | yes | 0 | - | - | 5 | 21235 | 10.7 |
| q22 | none | yes | yes | yes | 0 | - | - | 2 | 11589 | 6.0 |

Pages opened, in order:

- q01: tree/commands.py
- q02: summarize/pool.py > README.md
- q03: crypto/tokens.py > migrations/0002_users.sql
- q04: none
- q05: none
- q06: recall/fusion.py
- q07: recall/fusion.py
- q08: none
- q09: none
- q10: none
- q11: none
- q12: split/constants.py
- q13: split/constants.py
- q14: validation/git_auth.py
- q15: hrono/paths.py
- q16: none
- q17: none
- q18: export/collapse.py
- q19: profile/store.py
- q20: none
- q21: none
- q22: none

## Failed paths

### before-2 / q17: How many update runs may a chunk wait in the incubator pool before it is forced out?

- expected: 5, five in src/hrono/cluster/incubator.py
- answered: 5 update runs (`MAX_AGE = 5`). A chunk pending longer than that is force-assigned out of the incubator pool.
- cited: reference-for-hrono-a-python-project-that-builds-a-topic-tre-13/src-hrono-cluster-incubator-py-18.md (repository path: src/hrono/cluster/incubator.py)
- tools in order: Read > Grep > Grep
- pages opened in order:
  1. `root.md`

### after-2 / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs the CLI in `paths.cli_workdir`, an empty directory that hrono owns, because the CLI reads the project memory of its working directory. Running from a directory hrono controls keeps that memory out of the calls, as a second lock alongside `--safe-mode`.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Grep > Grep
- pages opened in order:
  1. `root.md`
