# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob,Grep. 22 questions x 4 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| levels-2 | 21/22 | 22/22 | 21/22 | 1.3 | 1.9 | 8/19 | 619880 | 13899 | 8.8 | 1.06 |
| levels-3 | 21/22 | 22/22 | 21/22 | 1.1 | 1.8 | 5/19 | 538647 | 13711 | 8.5 | 0.97 |
| levels-4 | 20/22 | 22/22 | 20/22 | 1.1 | 2.0 | 5/19 | 547181 | 13269 | 8.4 | 0.94 |
| raw | 21/22 | 21/22 | 22/22 | 0.5 | 1.0 | 8/19 | 340982 | 11485 | 8.4 | 0.42 |

levels-3 and levels-4 are byte-identical folders: what differs between them is the agent's own variance.

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "The canary word is **PELICAN-7731**, and the skill is `graphify` (`/graphify`, in `~/.claude/skills/graphify/SKILL.md`). Other names I can see: - **Hook:** `sensitive-canary` (0.8.2 available, 0.8.1 vendored) and its `/update-canary` command. - **Plexus repos and systems:** `website-monoreact`, `web"
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "No canary words, skill names or memory-file codes appear in my instructions. The distinctive names that do appear are: - **Tool names:** Glob, Grep, Read. These are the three tools defined for me. My instructions also mention deferred tools, but they don't name any. - **Other identifiers in the cont"
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### levels-2 (export, `/Users/orest/repos/hrono/.claude/worktrees/E004/.e2e/eval/runs/2026-10-03/levels-2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 1 | 3 | 27507 | 8.7 |
| q02 | shallow | yes | yes | yes | 1 | - | - | 2 | 15227 | 7.4 |
| q03 | shallow | yes | yes | yes | 3 | 2 | 1 | 4 | 35374 | 11.6 |
| q04 | deep | yes | yes | yes | 1 | - | - | 2 | 26399 | 7.4 |
| q05 | deep | yes | yes | yes | 0 | - | - | 1 | 7296 | 6.2 |
| q06 | deep | yes | yes | yes | 1 | - | - | 3 | 32382 | 10.3 |
| q07 | deep | yes | yes | yes | 2 | 2 | 1 | 3 | 27886 | 9.7 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 9057 | 5.9 |
| q09 | deep | yes | yes | yes | 2 | - | - | 4 | 35465 | 9.4 |
| q10 | deep | yes | yes | yes | 2 | 2 | 1 | 5 | 59885 | 14.7 |
| q11 | deep | yes | yes | yes | 2 | 2 | 1 | 3 | 30753 | 8.2 |
| q12 | shallow | yes | yes | yes | 1 | - | - | 2 | 15813 | 6.8 |
| q13 | deep | no | yes | no | 1 | - | - | 2 | 17824 | 6.1 |
| q14 | deep | yes | yes | yes | 1 | 1 | 1 | 2 | 11308 | 7.7 |
| q15 | deep | yes | yes | yes | 2 | 2 | 1 | 6 | 66465 | 16.4 |
| q16 | deep | yes | yes | yes | 1 | - | - | 3 | 28608 | 8.5 |
| q17 | deep | yes | yes | yes | 1 | - | - | 3 | 31515 | 7.6 |
| q18 | deep | yes | yes | yes | 2 | 2 | 1 | 3 | 33244 | 8.6 |
| q19 | shallow | yes | yes | yes | 1 | - | - | 2 | 25686 | 7.7 |
| q20 | none | yes | yes | yes | 1 | - | - | 3 | 25560 | 8.4 |
| q21 | none | yes | yes | yes | 1 | - | - | 3 | 25962 | 9.0 |
| q22 | none | yes | yes | yes | 1 | - | - | 3 | 30664 | 7.5 |

Pages opened, in order:

- q01: root.md > 14/src-hrono-tree-commands-py-260.md
- q02: root.md
- q03: root.md > 15/src-hrono-crypto-tokens-py-36.md > 9/src-hrono-db-migrations-0002-users-sql-44.md
- q04: root.md
- q05: none
- q06: root.md
- q07: root.md > 11/src-hrono-recall-fusion-py-149.md
- q08: none
- q09: root.md > 13/brief.md
- q10: root.md > 12/src-hrono-summarize-propagate-py-253.md
- q11: root.md > 10/src-hrono-jobs-worker-py-129.md
- q12: root.md
- q13: root.md
- q14: 5/src-hrono-registry-validation-git-auth-py-170.md
- q15: root.md > 15/src-hrono-paths-py-140.md
- q16: root.md
- q17: root.md
- q18: root.md > 16/src-hrono-export-collapse-py-89.md
- q19: root.md
- q20: root.md
- q21: root.md
- q22: root.md

### levels-3 (export, `/Users/orest/repos/hrono/.claude/worktrees/E004/.e2e/eval/runs/2026-10-03/levels-3`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 2 | 3 | 24927 | 9.1 |
| q02 | shallow | yes | yes | yes | 0 | - | - | 1 | 7648 | 6.1 |
| q03 | shallow | yes | yes | yes | 2 | - | - | 3 | 38322 | 12.1 |
| q04 | deep | no | yes | no | 1 | - | - | 2 | 25245 | 8.0 |
| q05 | deep | yes | yes | yes | 0 | - | - | 1 | 7576 | 5.8 |
| q06 | deep | yes | yes | yes | 2 | 2 | 2 | 3 | 33728 | 10.1 |
| q07 | deep | yes | yes | yes | 1 | - | - | 3 | 23863 | 8.9 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 9985 | 5.8 |
| q09 | deep | yes | yes | yes | 1 | - | - | 3 | 32359 | 9.2 |
| q10 | deep | yes | yes | yes | 1 | - | - | 4 | 41771 | 12.9 |
| q11 | deep | yes | yes | yes | 1 | - | - | 2 | 16228 | 7.0 |
| q12 | shallow | yes | yes | yes | 1 | - | - | 2 | 17383 | 7.0 |
| q13 | deep | yes | yes | yes | 1 | - | - | 2 | 16771 | 6.1 |
| q14 | deep | yes | yes | yes | 1 | 1 | 2 | 2 | 12024 | 7.6 |
| q15 | deep | yes | yes | yes | 3 | 2 | 2 | 4 | 26279 | 10.5 |
| q16 | deep | yes | yes | yes | 1 | - | - | 4 | 48263 | 11.7 |
| q17 | deep | yes | yes | yes | 1 | - | - | 4 | 30401 | 9.9 |
| q18 | deep | yes | yes | yes | 2 | 2 | 2 | 3 | 35349 | 9.0 |
| q19 | shallow | yes | yes | yes | 1 | - | - | 2 | 14094 | 7.0 |
| q20 | none | yes | yes | yes | 1 | - | - | 2 | 12917 | 6.2 |
| q21 | none | yes | yes | yes | 1 | - | - | 4 | 33045 | 9.8 |
| q22 | none | yes | yes | yes | 1 | - | - | 3 | 30469 | 8.3 |

Pages opened, in order:

- q01: root.md > 14/src-hrono-tree-commands-py-260.md
- q02: none
- q03: root.md > 9/src-hrono-db-migrations-0002-users-sql-44.md
- q04: root.md
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
- q15: root.md > 15/src-hrono-paths-py-140.md > 6/src-hrono-llm-providers-py-136.md
- q16: root.md
- q17: root.md
- q18: root.md > 16/src-hrono-export-collapse-py-89.md
- q19: root.md
- q20: root.md
- q21: root.md
- q22: root.md

### levels-4 (export, `/Users/orest/repos/hrono/.claude/worktrees/E004/.e2e/eval/runs/2026-10-03/levels-4`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 2 | 3 | 24802 | 8.7 |
| q02 | shallow | yes | yes | yes | 1 | - | - | 2 | 13808 | 6.1 |
| q03 | shallow | yes | yes | yes | 3 | 3 | 2 | 4 | 34899 | 10.6 |
| q04 | deep | yes | yes | yes | 1 | - | - | 2 | 24007 | 7.6 |
| q05 | deep | yes | yes | yes | 0 | - | - | 1 | 7633 | 6.1 |
| q06 | deep | yes | yes | yes | 2 | 2 | 2 | 3 | 31029 | 9.1 |
| q07 | deep | no | yes | no | 1 | - | - | 3 | 23218 | 8.5 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 9973 | 6.0 |
| q09 | deep | yes | yes | yes | 1 | - | - | 3 | 32384 | 9.1 |
| q10 | deep | yes | yes | yes | 1 | - | - | 4 | 36405 | 13.4 |
| q11 | deep | yes | yes | yes | 1 | - | - | 2 | 16016 | 6.1 |
| q12 | shallow | yes | yes | yes | 1 | - | - | 2 | 14530 | 6.4 |
| q13 | deep | yes | yes | yes | 1 | - | - | 3 | 32039 | 7.9 |
| q14 | deep | yes | yes | yes | 1 | 1 | 2 | 2 | 11212 | 7.6 |
| q15 | deep | yes | yes | yes | 2 | 2 | 2 | 6 | 60249 | 16.6 |
| q16 | deep | yes | yes | yes | 1 | - | - | 3 | 26708 | 8.3 |
| q17 | deep | yes | yes | yes | 1 | - | - | 3 | 29882 | 9.0 |
| q18 | deep | yes | yes | yes | 1 | - | - | 3 | 29835 | 8.6 |
| q19 | shallow | no | yes | no | 1 | - | - | 1 | 12735 | 5.9 |
| q20 | none | yes | yes | yes | 1 | - | - | 3 | 23317 | 7.1 |
| q21 | none | yes | yes | yes | 1 | - | - | 3 | 22705 | 7.8 |
| q22 | none | yes | yes | yes | 1 | - | - | 3 | 29795 | 7.8 |

Pages opened, in order:

- q01: root.md > 14/src-hrono-tree-commands-py-260.md
- q02: root.md
- q03: root.md > 9/src-hrono-db-migrations-0002-users-sql-44.md > 15/src-hrono-crypto-tokens-py-36.md
- q04: root.md
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
- q15: root.md > 15/src-hrono-paths-py-140.md
- q16: root.md
- q17: root.md
- q18: root.md
- q19: root.md
- q20: root.md
- q21: root.md
- q22: root.md

### raw (raw, `/Users/orest/repos/hrono/.claude/worktrees/E004/.e2e/eval/runs/2026-10-03/raw`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 1 | 1 | 3 | 3 | 21149 | 9.3 |
| q02 | shallow | yes | yes | yes | 2 | 1 | 3 | 3 | 13120 | 8.3 |
| q03 | shallow | yes | yes | yes | 3 | 1 | 3 | 4 | 15755 | 11.2 |
| q04 | deep | yes | yes | yes | 0 | - | - | 2 | 10872 | 6.7 |
| q05 | deep | yes | yes | yes | 0 | - | - | 2 | 10712 | 7.0 |
| q06 | deep | yes | yes | yes | 0 | - | - | 1 | 8805 | 6.6 |
| q07 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 12957 | 7.9 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 8353 | 5.5 |
| q09 | deep | yes | yes | yes | 0 | - | - | 2 | 15316 | 7.2 |
| q10 | deep | yes | yes | yes | 1 | 1 | 3 | 5 | 25932 | 12.3 |
| q11 | deep | yes | yes | yes | 0 | - | - | 2 | 12041 | 6.8 |
| q12 | shallow | yes | yes | yes | 1 | - | - | 5 | 40960 | 13.3 |
| q13 | deep | yes | yes | yes | 0 | - | - | 2 | 11620 | 7.6 |
| q14 | deep | yes | yes | yes | 1 | 1 | 4 | 2 | 11040 | 7.8 |
| q15 | deep | no | no | yes | 0 | - | - | 3 | 11639 | 8.5 |
| q16 | deep | yes | yes | yes | 0 | - | - | 3 | 11281 | 7.2 |
| q17 | deep | yes | yes | yes | 0 | - | - | 2 | 14005 | 7.8 |
| q18 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 20549 | 9.4 |
| q19 | shallow | yes | yes | yes | 1 | 1 | 3 | 4 | 20069 | 10.3 |
| q20 | none | yes | yes | yes | 0 | - | - | 2 | 12029 | 6.8 |
| q21 | none | yes | yes | yes | 0 | - | - | 5 | 21213 | 11.2 |
| q22 | none | yes | yes | yes | 0 | - | - | 2 | 11565 | 6.4 |

Pages opened, in order:

- q01: tree/commands.py
- q02: summarize/pool.py > README.md
- q03: crypto/tokens.py > migrations/0002_users.sql > auth/users.py
- q04: none
- q05: none
- q06: none
- q07: recall/fusion.py
- q08: none
- q09: none
- q10: summarize/propagate.py
- q11: none
- q12: split/pack.py
- q13: none
- q14: validation/git_auth.py
- q15: none
- q16: none
- q17: none
- q18: export/collapse.py
- q19: profile/store.py
- q20: none
- q21: none
- q22: none

## Failed paths

### levels-2 / q13: What section size budget, in bytes, applies to files in the data category (as opposed to code and docs)?

- expected: 2048, 2 kb, 2kb in src/hrono/ingest/split/constants.py, GLOSSARY.md
- answered: Files in the data category have a section size budget of 2048 bytes. Code and docs use 10240 bytes, and `section_budget(path)` picks the budget by extension category, defaulting to docs.
- cited: this-is-the-hrono-contributor-guide-plus-a-set-of-condensed--3/brief.md
- tools in order: Read > Grep
- pages opened in order:
  1. `root.md`

### levels-3 / q04: In the export, how many entries is one index page budgeted to list?

- expected: 40 in src/hrono/export/collapse.py
- answered: 40 entries per page (WIDTH=40).
- cited: root.md
- tools in order: Read > Grep
- pages opened in order:
  1. `root.md`

### levels-4 / q07: What is the largest share of the recall window that passages from one document may take?

- expected: 0.4, 40%, 40 % in src/hrono/recall/fusion.py
- answered: Up to 40% of the recall window per document, applied as a reserve and not a hard cap.
- cited: hrono-source-ingestion-schema-recall-and-clustering-parent-b-20/these-condensations-together-describe-recall-milestone-m5-in-11/brief.md
- tools in order: Read > Grep > Grep
- pages opened in order:
  1. `root.md`

### levels-4 / q19: Which environment variable moves the CLI's profile config file to another directory?

- expected: HRONO_HOME in src/hrono/profile/store.py
- answered: `HRONO_HOME` sets the directory that holds the CLI's profile `config.toml`. If it is unset, the default is `~/.hrono`.
- cited: root.md
- tools in order: Read
- pages opened in order:
  1. `root.md`

### raw / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs in `paths.cli_workdir`, an empty directory owned by hrono, because the CLI reads the project memory of its working directory and this keeps foreign project memory out of the calls.
- cited: src/hrono/llm/claude_code.py
- tools in order: Grep > Glob > Grep
- pages opened in order:
