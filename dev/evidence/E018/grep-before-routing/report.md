# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob,Grep. 22 questions x 3 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| levels-2 | 22/22 | 22/22 | 22/22 | 1.4 | 2.0 | 8/19 | 849526 | 14842 | 9.1 | 1.47 |
| levels-3 | 22/22 | 22/22 | 22/22 | 1.2 | 1.9 | 7/19 | 973608 | 14440 | 9.7 | 1.71 |
| raw | 21/22 | 21/22 | 22/22 | 0.5 | 1.0 | 9/19 | 299368 | 10577 | 7.5 | 0.39 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "The distinctive items are the canary word **PELICAN-7731** (from the project CLAUDE.md) and the `graphify` skill, which is triggered by `/graphify` and invoked through the Skill tool. Other names that appear: - **Hooks:** `sensitive-canary` (0.8.2 available, 0.8.1 vendored) and the `/update-canary` "
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "I found no canary words, codes, skill names or memory files. The distinctive items in my instructions are: - **Tool names:** Glob, Grep, Read. The instructions also mention deferred tools, but none are named. - **Model identifiers:** "Sonnet 5.5" and "claude-sonnet-5-5". - **Environment details:** t"
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### levels-2 (export, `/Users/orest/repos/hrono/.claude/worktrees/E018/.scratch/run/levels-2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 1 | 3 | 36417 | 8.5 |
| q02 | shallow | yes | yes | yes | 1 | - | - | 3 | 35674 | 8.2 |
| q03 | shallow | yes | yes | yes | 4 | 2 | 1 | 5 | 46159 | 12.1 |
| q04 | deep | yes | yes | yes | 1 | - | - | 4 | 70126 | 12.2 |
| q05 | deep | yes | yes | yes | 0 | - | - | 3 | 16817 | 8.9 |
| q06 | deep | yes | yes | yes | 1 | - | - | 3 | 41911 | 9.6 |
| q07 | deep | yes | yes | yes | 1 | - | - | 3 | 38097 | 9.2 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 11211 | 5.5 |
| q09 | deep | yes | yes | yes | 1 | - | - | 3 | 43598 | 7.8 |
| q10 | deep | yes | yes | yes | 2 | 2 | 1 | 4 | 57330 | 11.6 |
| q11 | deep | yes | yes | yes | 1 | - | - | 2 | 21499 | 5.8 |
| q12 | shallow | yes | yes | yes | 2 | 2 | 1 | 3 | 38731 | 7.8 |
| q13 | deep | yes | yes | yes | 1 | - | - | 3 | 41112 | 9.0 |
| q14 | deep | yes | yes | yes | 1 | 1 | 1 | 2 | 12205 | 7.9 |
| q15 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 38002 | 12.3 |
| q16 | deep | yes | yes | yes | 1 | - | - | 3 | 37186 | 8.7 |
| q17 | deep | yes | yes | yes | 1 | - | - | 3 | 40982 | 8.8 |
| q18 | deep | yes | yes | yes | 2 | 2 | 1 | 4 | 63060 | 10.6 |
| q19 | shallow | yes | yes | yes | 2 | 2 | 1 | 3 | 36045 | 9.3 |
| q20 | none | yes | yes | yes | 1 | - | - | 3 | 34401 | 8.6 |
| q21 | none | yes | yes | yes | 1 | - | - | 4 | 50125 | 11.2 |
| q22 | none | yes | yes | yes | 1 | - | - | 3 | 38838 | 7.5 |

Pages opened, in order:

- q01: root.md > 14/src-hrono-tree-commands-py-528.md
- q02: root.md
- q03: root.md > 15/src-hrono-crypto-tokens-py-304.md > 9/src-hrono-db-migrations-0002-users-sql-312.md > 15/src-hrono-auth-users-py-279.md
- q04: root.md
- q05: none
- q06: root.md
- q07: root.md
- q08: none
- q09: root.md
- q10: root.md > 12/src-hrono-summarize-propagate-py-521.md
- q11: root.md
- q12: root.md > 3/src-hrono-ingest-split-constants-py-379.md
- q13: root.md
- q14: 5/src-hrono-registry-validation-git-auth-py-438.md
- q15: root.md > 6/src-hrono-llm-providers-py-404.md > 15/src-hrono-paths-py-408.md
- q16: root.md
- q17: root.md
- q18: root.md > 16/src-hrono-export-collapse-py-357.md
- q19: root.md > 15/src-hrono-profile-store-py-411.md
- q20: root.md
- q21: root.md
- q22: root.md

### levels-3 (export, `/Users/orest/repos/hrono/.claude/worktrees/E018/.scratch/run/levels-3`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 2 | 3 | 42593 | 9.4 |
| q02 | shallow | yes | yes | yes | 1 | - | - | 3 | 42387 | 10.3 |
| q03 | shallow | yes | yes | yes | 2 | 2 | 2 | 3 | 64005 | 18.5 |
| q04 | deep | yes | yes | yes | 2 | 2 | 2 | 4 | 61382 | 11.1 |
| q05 | deep | yes | yes | yes | 0 | - | - | 2 | 12401 | 10.9 |
| q06 | deep | yes | yes | yes | 1 | - | - | 2 | 44901 | 10.0 |
| q07 | deep | yes | yes | yes | 1 | - | - | 3 | 44476 | 10.1 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 10065 | 6.4 |
| q09 | deep | yes | yes | yes | 1 | - | - | 3 | 47065 | 9.5 |
| q10 | deep | yes | yes | yes | 2 | 2 | 2 | 5 | 93529 | 15.6 |
| q11 | deep | yes | yes | yes | 1 | - | - | 2 | 25506 | 6.4 |
| q12 | shallow | yes | yes | yes | 1 | - | - | 2 | 25783 | 6.7 |
| q13 | deep | yes | yes | yes | 1 | - | - | 3 | 50059 | 8.1 |
| q14 | deep | yes | yes | yes | 1 | 1 | 2 | 2 | 11201 | 7.1 |
| q15 | deep | yes | yes | yes | 2 | 2 | 2 | 6 | 105744 | 16.8 |
| q16 | deep | yes | yes | yes | 1 | - | - | 3 | 44707 | 8.8 |
| q17 | deep | yes | yes | yes | 1 | - | - | 3 | 47127 | 9.6 |
| q18 | deep | yes | yes | yes | 2 | 2 | 2 | 3 | 50012 | 8.7 |
| q19 | shallow | yes | yes | yes | 1 | - | - | 2 | 40739 | 9.0 |
| q20 | none | yes | yes | yes | 1 | - | - | 2 | 21932 | 6.2 |
| q21 | none | yes | yes | yes | 1 | - | - | 3 | 40794 | 8.1 |
| q22 | none | yes | yes | yes | 1 | - | - | 3 | 47200 | 7.0 |

Pages opened, in order:

- q01: root.md > 14/src-hrono-tree-commands-py-528.md
- q02: root.md
- q03: root.md > 15/src-hrono-auth-users-py-279.md
- q04: root.md > 16/src-hrono-export-collapse-py-357.md
- q05: none
- q06: root.md
- q07: root.md
- q08: none
- q09: root.md
- q10: root.md > 12/src-hrono-summarize-propagate-py-521.md
- q11: root.md
- q12: root.md
- q13: root.md
- q14: 5/src-hrono-registry-validation-git-auth-py-438.md
- q15: root.md > 15/src-hrono-paths-py-408.md
- q16: root.md
- q17: root.md
- q18: root.md > 16/src-hrono-export-collapse-py-357.md
- q19: root.md
- q20: root.md
- q21: root.md
- q22: root.md

### raw (raw, `/Users/orest/repos/hrono/.claude/worktrees/E018/.scratch/run/raw`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 0 | - | - | 2 | 15416 | 7.1 |
| q02 | shallow | yes | yes | yes | 2 | 1 | 3 | 3 | 13574 | 7.8 |
| q03 | shallow | yes | yes | yes | 2 | 1 | 3 | 3 | 13640 | 9.5 |
| q04 | deep | yes | yes | yes | 0 | - | - | 5 | 22964 | 10.1 |
| q05 | deep | yes | yes | yes | 0 | - | - | 2 | 10725 | 6.3 |
| q06 | deep | yes | yes | yes | 0 | - | - | 1 | 8687 | 5.8 |
| q07 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 12909 | 7.7 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 8017 | 5.0 |
| q09 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 15970 | 6.8 |
| q10 | deep | yes | yes | yes | 1 | 1 | 3 | 5 | 25397 | 12.4 |
| q11 | deep | yes | yes | yes | 0 | - | - | 2 | 12095 | 6.9 |
| q12 | shallow | yes | yes | yes | 0 | - | - | 1 | 8980 | 5.1 |
| q13 | deep | yes | yes | yes | 0 | - | - | 1 | 7812 | 5.7 |
| q14 | deep | yes | yes | yes | 1 | 1 | 4 | 2 | 11037 | 7.2 |
| q15 | deep | no | no | yes | 0 | - | - | 3 | 11659 | 8.1 |
| q16 | deep | yes | yes | yes | 0 | - | - | 1 | 7015 | 5.5 |
| q17 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 24934 | 10.4 |
| q18 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 20551 | 8.6 |
| q19 | shallow | yes | yes | yes | 1 | 1 | 3 | 2 | 11816 | 7.7 |
| q20 | none | yes | yes | yes | 0 | - | - | 2 | 11215 | 6.6 |
| q21 | none | yes | yes | yes | 0 | - | - | 3 | 10483 | 6.9 |
| q22 | none | yes | yes | yes | 0 | - | - | 2 | 14472 | 6.7 |

Pages opened, in order:

- q01: none
- q02: summarize/pool.py > README.md
- q03: crypto/tokens.py > migrations/0002_users.sql
- q04: none
- q05: none
- q06: none
- q07: recall/fusion.py
- q08: none
- q09: cluster/repair.py
- q10: summarize/propagate.py
- q11: none
- q12: none
- q13: none
- q14: validation/git_auth.py
- q15: none
- q16: none
- q17: cluster/incubator.py
- q18: export/collapse.py
- q19: profile/store.py
- q20: none
- q21: none
- q22: none

## Failed paths

### raw / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs in hrono's own `paths.cli_workdir`, an empty directory that hrono owns. It runs there because the CLI reads the PROJECT MEMORY of its working directory, so a directory hrono owns keeps outside project memory out of the calls.
- cited: src/hrono/llm/claude_code.py
- tools in order: Grep > Glob > Grep
- pages opened in order:
