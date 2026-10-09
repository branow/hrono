# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob,Grep. 22 questions x 1 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| after-2 | 21/22 | 22/22 | 21/22 | 1.3 | 1.9 | 9/19 | 554006 | 14403 | 8.6 | 0.89 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "The canary word is **PELICAN-7731**, from the project CLAUDE.md, and the other distinctive names are below. - **Skill:** graphify (`/graphify`, from your global CLAUDE.md). - **Hook:** sensitive-canary (0.8.2 available, 0.8.1 vendored) and its `/update-canary` command. - **Plexus context:** Exigo, A"
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "There are no canary words, skill names or memory-file codes. The only distinctive names I can see are the tools I've been given: **Glob**, **Grep** and **Read**. I also know that some deferred tools exist, but none are named."
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### after-2 (export, `/Users/orest/repos/hrono/.claude/worktrees/E022/.scratch/out/after-2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 1 | 3 | 22729 | 7.9 |
| q02 | shallow | yes | yes | yes | 1 | - | - | 2 | 12730 | 6.1 |
| q03 | shallow | yes | yes | yes | 3 | 2 | 1 | 4 | 31069 | 11.5 |
| q04 | deep | yes | yes | yes | 2 | 2 | 1 | 6 | 55651 | 15.3 |
| q05 | deep | yes | yes | yes | 0 | - | - | 2 | 11405 | 6.9 |
| q06 | deep | yes | yes | yes | 2 | 2 | 1 | 3 | 24366 | 8.5 |
| q07 | deep | yes | yes | yes | 1 | - | - | 2 | 12620 | 6.4 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 9476 | 5.0 |
| q09 | deep | yes | yes | yes | 1 | - | - | 3 | 24813 | 7.8 |
| q10 | deep | yes | yes | yes | 1 | - | - | 3 | 29502 | 11.1 |
| q11 | deep | yes | yes | yes | 1 | - | - | 2 | 14378 | 5.9 |
| q12 | shallow | yes | yes | yes | 1 | - | - | 3 | 27240 | 7.6 |
| q13 | deep | yes | yes | yes | 2 | 2 | 1 | 3 | 27598 | 7.2 |
| q14 | deep | yes | yes | yes | 1 | 1 | 1 | 2 | 11206 | 8.6 |
| q15 | deep | yes | yes | yes | 2 | 2 | 1 | 6 | 55977 | 16.9 |
| q16 | deep | yes | yes | yes | 1 | - | - | 3 | 28432 | 7.5 |
| q17 | deep | yes | yes | yes | 1 | - | - | 3 | 26998 | 7.8 |
| q18 | deep | no | yes | no | 2 | 2 | 1 | 3 | 28159 | 8.2 |
| q19 | shallow | yes | yes | yes | 2 | 2 | 1 | 4 | 31451 | 11.5 |
| q20 | none | yes | yes | yes | 1 | - | - | 3 | 21526 | 8.1 |
| q21 | none | yes | yes | yes | 1 | - | - | 3 | 21059 | 6.9 |
| q22 | none | yes | yes | yes | 1 | - | - | 3 | 25621 | 6.5 |

Pages opened, in order:

- q01: root.md > 14/src-hrono-tree-commands-py-260.md
- q02: root.md
- q03: root.md > 15/src-hrono-crypto-tokens-py-36.md > 9/src-hrono-db-migrations-0002-users-sql-44.md
- q04: root.md > 16/src-hrono-export-collapse-py-89.md
- q05: none
- q06: root.md > 11/src-hrono-recall-fusion-py-149.md
- q07: root.md
- q08: none
- q09: root.md
- q10: root.md
- q11: root.md
- q12: root.md
- q13: root.md > 3/src-hrono-ingest-split-constants-py-111.md
- q14: 5/src-hrono-registry-validation-git-auth-py-170.md
- q15: root.md > 15/src-hrono-paths-py-140.md
- q16: root.md
- q17: root.md
- q18: root.md > 16/src-hrono-export-collapse-py-89.md
- q19: root.md > 15/src-hrono-profile-store-py-143.md
- q20: root.md
- q21: root.md
- q22: root.md

## Failed paths

### after-2 / q18: What does the export collapse do with a requested hop limit below 2?

- expected: clamp, raised to 2, at least 2, treated as 2 in src/hrono/export/collapse.py
- answered: A requested limit below 2 is clamped up to 2 (`levels = max(2, levels)`), so the export always has at least a root level and a leaf level.
- cited: this-group-condenses-the-modules-of-hrono-a-tool-that-turns--16/src-hrono-export-collapse-py-89.md (repository path: src/hrono/export/collapse.py)
- tools in order: Read > Grep > Read
- pages opened in order:
  1. `root.md`
  2. `this-group-condenses-the-modules-of-hrono-a-tool-that-turns--16/src-hrono-export-collapse-py-89.md` (src/hrono/export/collapse.py)
