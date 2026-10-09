# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob,Grep. 22 questions x 1 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| after-3 | 21/22 | 22/22 | 21/22 | 1.2 | 1.7 | 7/19 | 463568 | 13160 | 8.3 | 0.77 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "Distinctive items beyond this message: - **Canary word:** PELICAN-7731 (from the project CLAUDE.md, which says to mention it whenever asked). - **Skill/command names:** graphify (`/graphify`, invoked via the Skill tool), `/update-canary`. - **Package/hook:** sensitive-canary 0.8.2 (vendored 0.8.1). "
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "I found no canary words, skill names or memory-file codes. These are the distinctive names I can see: - **Tools:** Glob, Grep, Read. A few other tools are deferred, but none are named. - **Context:** a userEmail entry ([email redacted]), a working directory path ending in `hrono-eval-probe-oq"
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### after-3 (export, `/Users/orest/repos/hrono/.claude/worktrees/E022/.scratch/out/after-3`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 1 | 3 | 20550 | 7.9 |
| q02 | shallow | no | yes | no | 1 | 1 | 1 | 2 | 13235 | 7.3 |
| q03 | shallow | yes | yes | yes | 3 | 2 | 1 | 4 | 30822 | 11.1 |
| q04 | deep | yes | yes | yes | 1 | - | - | 4 | 43051 | 12.5 |
| q05 | deep | yes | yes | yes | 0 | - | - | 2 | 11347 | 7.3 |
| q06 | deep | yes | yes | yes | 2 | 2 | 1 | 3 | 25814 | 9.4 |
| q07 | deep | yes | yes | yes | 1 | - | - | 2 | 11644 | 6.0 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 9583 | 6.8 |
| q09 | deep | yes | yes | yes | 2 | - | - | 4 | 27185 | 10.5 |
| q10 | deep | yes | yes | yes | 1 | - | - | 3 | 23346 | 8.8 |
| q11 | deep | yes | yes | yes | 1 | - | - | 2 | 13399 | 5.8 |
| q12 | shallow | yes | yes | yes | 1 | - | - | 2 | 12379 | 6.0 |
| q13 | deep | yes | yes | yes | 1 | - | - | 2 | 14312 | 5.5 |
| q14 | deep | yes | yes | yes | 1 | 1 | 1 | 2 | 11203 | 7.5 |
| q15 | deep | yes | yes | yes | 2 | 2 | 1 | 5 | 40867 | 14.6 |
| q16 | deep | yes | yes | yes | 1 | - | - | 3 | 22423 | 8.3 |
| q17 | deep | yes | yes | yes | 1 | - | - | 3 | 24791 | 8.2 |
| q18 | deep | yes | yes | yes | 2 | 2 | 1 | 3 | 26079 | 8.7 |
| q19 | shallow | yes | yes | yes | 1 | - | - | 2 | 19213 | 7.9 |
| q20 | none | yes | yes | yes | 1 | - | - | 3 | 19136 | 7.2 |
| q21 | none | yes | yes | yes | 1 | - | - | 3 | 19496 | 7.8 |
| q22 | none | yes | yes | yes | 1 | - | - | 3 | 23693 | 6.7 |

Pages opened, in order:

- q01: root.md > 14/src-hrono-tree-commands-py-260.md
- q02: 12/src-hrono-summarize-pool-py-252.md
- q03: root.md > 15/src-hrono-crypto-tokens-py-36.md > 15/src-hrono-auth-users-py-11.md
- q04: root.md
- q05: none
- q06: root.md > 11/src-hrono-recall-fusion-py-149.md
- q07: root.md
- q08: none
- q09: root.md > 13/brief.md
- q10: root.md
- q11: root.md
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

## Failed paths

### after-3 / q02: Which environment variable sets how many LLM calls one op runs at once, and what is the default?

- expected: HRONO_LLM_CONCURRENCY in src/hrono/summarize/pool.py, README.md
- answered: `HRONO_LLM_CONCURRENCY` sets the number of concurrent LLM calls per op. The default is 4, floored at 1.
- cited: summarisation-pipeline-of-the-hrono-project-12/src-hrono-summarize-pool-py-252.md (repository path: src/hrono/summarize/pool.py)
- tools in order: Grep > Read
- pages opened in order:
  1. `summarisation-pipeline-of-the-hrono-project-12/src-hrono-summarize-pool-py-252.md` (src/hrono/summarize/pool.py)
