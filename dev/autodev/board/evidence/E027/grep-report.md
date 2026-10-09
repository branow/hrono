# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob,Grep. 22 questions x 2 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| head | 21/22 | 22/22 | 21/22 | 1.3 | 1.8 | 9/19 | 534872 | 15017 | 9.1 | 0.80 |
| noroot | 20/22 | 21/22 | 21/22 | 1.1 | 1.8 | 4/19 | 429444 | 14147 | 8.5 | 0.67 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "The canary word is **PELICAN-7731**, from the project CLAUDE.md, which says to mention it whenever asked. The other distinctive names are the skill `graphify` (trigger `/graphify`) and the hook-reported `sensitive-canary` (0.8.2 available, vendored 0.8.1) with its `/update-canary` command. The Plexu"
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "There's no canary word, skill name or memory file in my instructions. The distinctive names they do mention are: - **Tools:** Glob, Grep, Read. The instructions also say some deferred tools exist, but none are named. - **Context:** a `userEmail` entry ([email redacted]), the environment detai"
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### head (export, `/Users/orest/repos/hrono/.claude/worktrees/E027/.scratch/out/base-l2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 1 | 3 | 19822 | 7.9 |
| q02 | shallow | yes | yes | yes | 0 | - | - | 2 | 11661 | 7.1 |
| q03 | shallow | yes | yes | yes | 3 | 2 | 1 | 5 | 46250 | 12.8 |
| q04 | deep | yes | yes | yes | 1 | - | - | 3 | 26593 | 8.8 |
| q05 | deep | yes | yes | yes | 0 | - | - | 2 | 11930 | 6.8 |
| q06 | deep | no | yes | no | 2 | 2 | 1 | 3 | 25934 | 8.9 |
| q07 | deep | yes | yes | yes | 1 | - | - | 3 | 20172 | 9.5 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 9315 | 5.5 |
| q09 | deep | yes | yes | yes | 2 | 2 | 1 | 6 | 68078 | 16.0 |
| q10 | deep | yes | yes | yes | 3 | 2 | 1 | 5 | 34526 | 12.9 |
| q11 | deep | yes | yes | yes | 1 | - | - | 2 | 12827 | 6.4 |
| q12 | shallow | yes | yes | yes | 1 | - | - | 3 | 26986 | 8.9 |
| q13 | deep | yes | yes | yes | 1 | - | - | 4 | 36183 | 10.1 |
| q14 | deep | yes | yes | yes | 1 | 1 | 1 | 2 | 11321 | 7.6 |
| q15 | deep | yes | yes | yes | 3 | 2 | 1 | 4 | 20518 | 12.6 |
| q16 | deep | yes | yes | yes | 1 | - | - | 3 | 21984 | 10.7 |
| q17 | deep | yes | yes | yes | 1 | - | - | 3 | 24477 | 8.9 |
| q18 | deep | yes | yes | yes | 1 | 1 | 1 | 2 | 18355 | 7.1 |
| q19 | shallow | yes | yes | yes | 2 | 2 | 1 | 4 | 28943 | 10.5 |
| q20 | none | yes | yes | yes | 1 | - | - | 3 | 18043 | 7.8 |
| q21 | none | yes | yes | yes | 1 | - | - | 3 | 17987 | 7.3 |
| q22 | none | yes | yes | yes | 1 | - | - | 3 | 22967 | 6.7 |

Pages opened, in order:

- q01: root.md > 17/src-hrono-tree-commands-py-293.md
- q02: none
- q03: root.md > 20/src-hrono-auth-users-py-12.md > 12/src-hrono-db-migrations-0002-users-sql-45.md
- q04: root.md
- q05: none
- q06: root.md > 13/src-hrono-recall-fusion-py-155.md
- q07: root.md
- q08: none
- q09: root.md > 6/src-hrono-cluster-repair-py-29.md
- q10: root.md > 14/src-hrono-summarize-propagate-py-285.md > 14/src-hrono-summarize-propagate-py-285.md
- q11: root.md
- q12: root.md
- q13: root.md
- q14: 4/src-hrono-registry-validation-git-auth-py-179.md
- q15: root.md > 19/src-hrono-paths-py-146.md > 3/src-hrono-llm-providers-py-142.md
- q16: root.md
- q17: root.md
- q18: 18/src-hrono-export-collapse-py-93.md
- q19: root.md > 19/src-hrono-profile-store-py-149.md
- q20: root.md
- q21: root.md
- q22: root.md

### noroot (export, `/Users/orest/repos/hrono/.claude/worktrees/E027/.scratch/out/noroot`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 1 | - | - | 3 | 16802 | 8.3 |
| q02 | shallow | yes | yes | yes | 0 | - | - | 2 | 12136 | 7.8 |
| q03 | shallow | yes | yes | yes | 4 | 2 | 1 | 5 | 42342 | 14.7 |
| q04 | deep | yes | yes | yes | 1 | - | - | 3 | 22837 | 9.0 |
| q05 | deep | yes | yes | yes | 0 | - | - | 2 | 11890 | 6.7 |
| q06 | deep | yes | yes | yes | 1 | - | - | 3 | 22328 | 9.6 |
| q07 | deep | yes | yes | yes | 1 | - | - | 3 | 18648 | 9.5 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 9132 | 5.4 |
| q09 | deep | yes | yes | yes | 2 | - | - | 5 | 35887 | 12.1 |
| q10 | deep | yes | yes | yes | 1 | - | - | 5 | 38761 | 15.0 |
| q11 | deep | yes | yes | yes | 1 | - | - | 2 | 11462 | 5.6 |
| q12 | shallow | yes | yes | yes | 1 | - | - | 3 | 23045 | 8.2 |
| q13 | deep | yes | yes | yes | 1 | - | - | 3 | 21396 | 7.2 |
| q14 | deep | no | yes | no | 1 | 1 | 1 | 2 | 11158 | 7.8 |
| q15 | deep | no | no | yes | 2 | 2 | 1 | 3 | 20242 | 9.0 |
| q16 | deep | yes | yes | yes | 1 | - | - | 2 | 11909 | 6.6 |
| q17 | deep | yes | yes | yes | 1 | - | - | 3 | 21179 | 8.1 |
| q18 | deep | yes | yes | yes | 2 | 2 | 1 | 3 | 23238 | 8.6 |
| q19 | shallow | yes | yes | yes | 1 | - | - | 2 | 9731 | 6.3 |
| q20 | none | yes | yes | yes | 1 | - | - | 3 | 15302 | 8.2 |
| q21 | none | yes | yes | yes | 1 | - | - | 3 | 15189 | 7.5 |
| q22 | none | yes | yes | yes | 1 | - | - | 2 | 14830 | 6.5 |

Pages opened, in order:

- q01: root.md
- q02: none
- q03: root.md > 20/src-hrono-auth-users-py-12.md > 12/src-hrono-db-migrations-0002-users-sql-45.md > 7/src-hrono-crypto-tokens-py-37.md
- q04: root.md
- q05: none
- q06: root.md
- q07: root.md
- q08: none
- q09: root.md > 2/src-hrono-server-templates-guide-html-231.md
- q10: root.md
- q11: root.md
- q12: root.md
- q13: root.md
- q14: 4/src-hrono-registry-validation-git-auth-py-179.md
- q15: root.md > 3/src-hrono-llm-claude-code-py-138.md
- q16: root.md
- q17: root.md
- q18: root.md > 18/src-hrono-export-collapse-py-93.md
- q19: root.md
- q20: root.md
- q21: root.md
- q22: root.md

## Failed paths

### head / q06: How does recall weight its vector leg against its keyword leg when fusing them?

- expected: 0.7 in src/hrono/recall/fusion.py
- answered: Weighted reciprocal rank fusion with k=60. The vector leg is weighted 0.7 and the keyword leg 0.3, giving score = 0.7/(60+vector_rank) + 0.3/(60+keyword_rank). A leg contributes only if the passage qualified in it, and the result is capped at 10 hits.
- cited: recall-m5-overview-this-group-documents-the-recall-pipeline-13/src-hrono-recall-fusion-py-155.md (repository path: src/hrono/recall/fusion.py)
- tools in order: Read > Grep > Read
- pages opened in order:
  1. `root.md`
  2. `recall-m5-overview-this-group-documents-the-recall-pipeline-13/src-hrono-recall-fusion-py-155.md` (src/hrono/recall/fusion.py)

### noroot / q14: When hrono runs git against a source, which environment variable does it set so git never prompts for credentials?

- expected: GIT_TERMINAL_PROMPT in src/hrono/registry/validation/git_auth.py
- answered: `GIT_TERMINAL_PROMPT=0`
- cited: hrono-s-registry-layer-for-external-facing-configuration-the-4/src-hrono-registry-validation-git-auth-py-179.md (repository path: src/hrono/registry/validation/git_auth.py)
- tools in order: Grep > Read
- pages opened in order:
  1. `hrono-s-registry-layer-for-external-facing-configuration-the-4/src-hrono-registry-validation-git-auth-py-179.md` (src/hrono/registry/validation/git_auth.py)

### noroot / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs in `paths.cli_workdir`, an empty directory hrono owns, because the CLI reads the PROJECT MEMORY of its working directory. Running there keeps that memory out of the summaries, as a second lock alongside `--safe-mode`.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Grep > Read
- pages opened in order:
  1. `root.md`
  2. `m4-text-completion-seam-3/src-hrono-llm-claude-code-py-138.md` (src/hrono/llm/claude_code.py)
