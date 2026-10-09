# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob,Grep. 22 questions x 3 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| levels-2 | 21/22 | 22/22 | 21/22 | 1.3 | 2.0 | 7/19 | 433528 | 14700 | 8.7 | 0.66 |
| levels-3 | 20/22 | 21/22 | 21/22 | 1.2 | 1.8 | 5/19 | 381917 | 14804 | 8.4 | 0.58 |
| raw | 22/22 | 22/22 | 22/22 | 0.5 | 1.0 | 9/19 | 320182 | 11569 | 7.8 | 0.40 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "The canary word is PELICAN-7731 (from the project CLAUDE.md, which says to mention it whenever asked). The other distinctive names are the **graphify** skill (`/graphify`, from your global CLAUDE.md) and the `sensitive-canary` hook (version 0.8.2 available, vendored 0.8.1, with the `/update-canary` "
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "There are no canary words, skill names or memory files. The distinctive names in my instructions are: - **Tools:** Glob, Grep, Read. The instructions also mention "deferred tools", but none are named. - **Product names:** Claude Agent SDK, Claude Code, and the model name Sonnet 5.5 (ID `claude-sonne"
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### levels-2 (export, `/Users/orest/repos/hrono/.claude/worktrees/E018/.scratch/run2/levels-2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 1 | 3 | 16755 | 8.6 |
| q02 | shallow | yes | yes | yes | 1 | - | - | 3 | 16256 | 8.1 |
| q03 | shallow | yes | yes | yes | 3 | 2 | 1 | 4 | 26135 | 11.4 |
| q04 | deep | yes | yes | yes | 1 | - | - | 3 | 21129 | 9.1 |
| q05 | deep | yes | yes | yes | 0 | - | - | 1 | 7516 | 5.2 |
| q06 | deep | yes | yes | yes | 1 | - | - | 2 | 12517 | 7.4 |
| q07 | deep | yes | yes | yes | 3 | 3 | 1 | 5 | 33340 | 11.0 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 9486 | 5.7 |
| q09 | deep | yes | yes | yes | 1 | - | - | 4 | 24825 | 9.4 |
| q10 | deep | yes | yes | yes | 2 | 2 | 1 | 6 | 39400 | 15.6 |
| q11 | deep | yes | yes | yes | 1 | - | - | 2 | 11276 | 6.1 |
| q12 | shallow | yes | yes | yes | 2 | 2 | 1 | 3 | 19107 | 8.2 |
| q13 | deep | yes | yes | yes | 1 | - | - | 4 | 28250 | 10.0 |
| q14 | deep | yes | yes | yes | 1 | 1 | 1 | 2 | 11160 | 7.4 |
| q15 | deep | yes | yes | yes | 2 | 2 | 1 | 5 | 31665 | 14.3 |
| q16 | deep | yes | yes | yes | 1 | - | - | 3 | 17553 | 8.2 |
| q17 | deep | yes | yes | yes | 1 | - | - | 3 | 21536 | 8.0 |
| q18 | deep | no | yes | no | 1 | - | - | 3 | 21066 | 8.4 |
| q19 | shallow | yes | yes | yes | 1 | - | - | 2 | 14871 | 7.6 |
| q20 | none | yes | yes | yes | 1 | - | - | 3 | 15680 | 8.2 |
| q21 | none | yes | yes | yes | 1 | - | - | 3 | 14616 | 7.4 |
| q22 | none | yes | yes | yes | 1 | - | - | 3 | 19389 | 6.6 |

Pages opened, in order:

- q01: root.md > 14/src-hrono-tree-commands-py-528.md
- q02: root.md
- q03: root.md > 15/src-hrono-crypto-tokens-py-304.md > 15/src-hrono-auth-users-py-279.md
- q04: root.md
- q05: none
- q06: root.md
- q07: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-417.md
- q08: none
- q09: root.md
- q10: root.md > 12/src-hrono-summarize-propagate-py-521.md
- q11: root.md
- q12: root.md > 3/src-hrono-ingest-split-constants-py-379.md
- q13: root.md
- q14: 5/src-hrono-registry-validation-git-auth-py-438.md
- q15: root.md > 15/src-hrono-paths-py-408.md
- q16: root.md
- q17: root.md
- q18: root.md
- q19: root.md
- q20: root.md
- q21: root.md
- q22: root.md

### levels-3 (export, `/Users/orest/repos/hrono/.claude/worktrees/E018/.scratch/run2/levels-3`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 2 | 3 | 15613 | 7.8 |
| q02 | shallow | yes | yes | yes | 0 | - | - | 1 | 8172 | 5.2 |
| q03 | shallow | yes | yes | yes | 4 | 2 | 2 | 5 | 27287 | 13.2 |
| q04 | deep | yes | yes | yes | 1 | - | - | 3 | 18285 | 9.3 |
| q05 | deep | yes | yes | yes | 0 | - | - | 2 | 12032 | 6.6 |
| q06 | deep | yes | yes | yes | 1 | - | - | 3 | 19785 | 8.8 |
| q07 | deep | no | yes | no | 1 | - | - | 3 | 12923 | 9.0 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 9884 | 5.3 |
| q09 | deep | yes | yes | yes | 2 | - | - | 5 | 39528 | 11.4 |
| q10 | deep | yes | yes | yes | 1 | - | - | 5 | 33694 | 13.6 |
| q11 | deep | yes | yes | yes | 1 | - | - | 2 | 10821 | 6.2 |
| q12 | shallow | yes | yes | yes | 2 | 2 | 2 | 3 | 16361 | 7.6 |
| q13 | deep | yes | yes | yes | 1 | - | - | 3 | 19447 | 7.8 |
| q14 | deep | yes | yes | yes | 1 | 1 | 2 | 2 | 11235 | 7.3 |
| q15 | deep | no | no | yes | 1 | - | - | 4 | 19240 | 11.6 |
| q16 | deep | yes | yes | yes | 1 | - | - | 3 | 15512 | 7.6 |
| q17 | deep | yes | yes | yes | 1 | - | - | 3 | 19069 | 8.8 |
| q18 | deep | yes | yes | yes | 2 | 2 | 2 | 3 | 19193 | 8.6 |
| q19 | shallow | yes | yes | yes | 1 | - | - | 2 | 8145 | 6.2 |
| q20 | none | yes | yes | yes | 1 | - | - | 3 | 15469 | 6.9 |
| q21 | none | yes | yes | yes | 1 | - | - | 3 | 12064 | 8.2 |
| q22 | none | yes | yes | yes | 1 | - | - | 3 | 18158 | 6.8 |

Pages opened, in order:

- q01: root.md > 14/src-hrono-tree-commands-py-528.md
- q02: none
- q03: root.md > 15/src-hrono-auth-users-py-279.md > 15/src-hrono-crypto-tokens-py-304.md > 9/src-hrono-db-migrations-0002-users-sql-312.md
- q04: root.md
- q05: none
- q06: root.md
- q07: root.md
- q08: none
- q09: root.md > 1/src-hrono-server-templates-base-html-470.md
- q10: root.md
- q11: root.md
- q12: root.md > 3/src-hrono-ingest-split-constants-py-379.md
- q13: root.md
- q14: 5/src-hrono-registry-validation-git-auth-py-438.md
- q15: root.md
- q16: root.md
- q17: root.md
- q18: root.md > 16/src-hrono-export-collapse-py-357.md
- q19: root.md
- q20: root.md
- q21: root.md
- q22: root.md

### raw (raw, `/Users/orest/repos/hrono/.claude/worktrees/E018/.scratch/run2/raw`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 1 | 1 | 3 | 3 | 25797 | 8.7 |
| q02 | shallow | yes | yes | yes | 2 | 1 | 3 | 3 | 13096 | 7.9 |
| q03 | shallow | yes | yes | yes | 2 | 1 | 3 | 4 | 19603 | 11.8 |
| q04 | deep | yes | yes | yes | 0 | - | - | 5 | 24060 | 10.4 |
| q05 | deep | yes | yes | yes | 0 | - | - | 2 | 10725 | 6.2 |
| q06 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 13574 | 7.8 |
| q07 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 12914 | 7.3 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 8348 | 5.2 |
| q09 | deep | yes | yes | yes | 0 | - | - | 2 | 13736 | 7.3 |
| q10 | deep | yes | yes | yes | 0 | - | - | 3 | 16351 | 9.3 |
| q11 | deep | yes | yes | yes | 0 | - | - | 2 | 12079 | 6.8 |
| q12 | shallow | yes | yes | yes | 0 | - | - | 1 | 9249 | 5.9 |
| q13 | deep | yes | yes | yes | 0 | - | - | 1 | 8784 | 5.4 |
| q14 | deep | yes | yes | yes | 1 | 1 | 4 | 2 | 11033 | 7.1 |
| q15 | deep | yes | yes | yes | 1 | 1 | 2 | 6 | 26573 | 13.9 |
| q16 | deep | yes | yes | yes | 0 | - | - | 2 | 7202 | 6.0 |
| q17 | deep | yes | yes | yes | 0 | - | - | 3 | 20128 | 9.2 |
| q18 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 20559 | 8.4 |
| q19 | shallow | yes | yes | yes | 1 | 1 | 3 | 2 | 12604 | 7.9 |
| q20 | none | yes | yes | yes | 0 | - | - | 2 | 11317 | 6.4 |
| q21 | none | yes | yes | yes | 0 | - | - | 3 | 10485 | 6.5 |
| q22 | none | yes | yes | yes | 0 | - | - | 3 | 11965 | 6.9 |

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
- q12: none
- q13: none
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

### levels-2 / q18: What does the export collapse do with a requested hop limit below 2?

- expected: clamp, raised to 2, at least 2, treated as 2 in src/hrono/export/collapse.py
- answered: It clamps the limit up to 2 (`levels = max(2, levels)`), so the export always has at least a root level and a section level.
- cited: hrono-topic-tree-system-a-stored-hierarchy-of-topics-and-sec-16/src-hrono-export-collapse-py-357.md (repository path: src/hrono/export/collapse.py)
- tools in order: Read > Grep > Grep
- pages opened in order:
  1. `root.md`

### levels-3 / q07: What is the largest share of the recall window that passages from one document may take?

- expected: 0.4, 40%, 40 % in src/hrono/recall/fusion.py
- answered: 40% of the recall window (4 of 10 slots) per document. Passages over that are deferred and only backfill leftover slots in a second pass.
- cited: hrono-parent-brief-20/hrono-s-recall-m5-pipeline-11/brief.md
- tools in order: Read > Grep > Grep
- pages opened in order:
  1. `root.md`

### levels-3 / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs in `paths.cli_workdir`, an empty directory owned by hrono. The CLI reads the PROJECT MEMORY of its working directory, so it must not run in an arbitrary directory. `--safe-mode` also guards against this, and the empty directory is a second lock.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Grep > Grep > Grep
- pages opened in order:
  1. `root.md`
