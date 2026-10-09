# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob,Grep. 22 questions x 2 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| head | 21/22 | 22/22 | 21/22 | 1.2 | 1.9 | 7/19 | 480106 | 13393 | 8.5 | 0.74 |
| noroot | 20/22 | 21/22 | 21/22 | 1.3 | 1.8 | 9/19 | 430045 | 13281 | 8.3 | 0.66 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "The distinctive items are the canary word **PELICAN-7731** (from the project CLAUDE.md) and the `graphify` skill, triggered by `/graphify`. The session hooks also mention `sensitive-canary` (vendored 0.8.1, 0.8.2 available) with its `/update-canary` command, and a `plexus-context` block naming repos"
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "There are no canary words, skill names or memory files. These are the distinctive names that appear in my instructions: - **Tools:** Glob, Grep, Read. The prompt also says some other tools are deferred, but it doesn't name them. - **Product and model names:** Claude Agent SDK, Claude Code, Sonnet 5."
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### head (export, `/Users/orest/repos/hrono/.claude/worktrees/E027/.scratch/out/base-l2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 1 | 3 | 19778 | 8.3 |
| q02 | shallow | yes | yes | yes | 0 | - | - | 2 | 13554 | 7.0 |
| q03 | shallow | yes | yes | yes | 3 | 2 | 1 | 4 | 30764 | 11.5 |
| q04 | deep | yes | yes | yes | 1 | - | - | 3 | 26559 | 9.0 |
| q05 | deep | yes | yes | yes | 0 | - | - | 2 | 11990 | 7.4 |
| q06 | deep | no | yes | no | 2 | 2 | 1 | 3 | 25641 | 9.4 |
| q07 | deep | yes | yes | yes | 1 | - | - | 3 | 19777 | 9.6 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 9070 | 5.4 |
| q09 | deep | yes | yes | yes | 1 | - | - | 3 | 25386 | 8.1 |
| q10 | deep | yes | yes | yes | 1 | - | - | 3 | 22144 | 9.4 |
| q11 | deep | yes | yes | yes | 1 | - | - | 2 | 12861 | 6.1 |
| q12 | shallow | yes | yes | yes | 1 | - | - | 2 | 12128 | 5.7 |
| q13 | deep | yes | yes | yes | 2 | 2 | 1 | 5 | 45851 | 12.0 |
| q14 | deep | yes | yes | yes | 1 | 1 | 1 | 2 | 11402 | 7.5 |
| q15 | deep | yes | yes | yes | 2 | 2 | 1 | 5 | 37418 | 13.9 |
| q16 | deep | yes | yes | yes | 1 | - | - | 3 | 21971 | 8.0 |
| q17 | deep | yes | yes | yes | 1 | - | - | 3 | 24622 | 8.3 |
| q18 | deep | yes | yes | yes | 2 | 2 | 1 | 3 | 24409 | 8.1 |
| q19 | shallow | yes | yes | yes | 1 | - | - | 3 | 25836 | 9.8 |
| q20 | none | yes | yes | yes | 1 | - | - | 3 | 17999 | 7.7 |
| q21 | none | yes | yes | yes | 1 | - | - | 3 | 17991 | 7.1 |
| q22 | none | yes | yes | yes | 1 | - | - | 3 | 22955 | 6.8 |

Pages opened, in order:

- q01: root.md > 17/src-hrono-tree-commands-py-293.md
- q02: none
- q03: root.md > 7/src-hrono-crypto-tokens-py-37.md > 20/src-hrono-auth-users-py-12.md
- q04: root.md
- q05: none
- q06: root.md > 13/src-hrono-recall-fusion-py-155.md
- q07: root.md
- q08: none
- q09: root.md
- q10: root.md
- q11: root.md
- q12: root.md
- q13: root.md > 8/src-hrono-ingest-split-constants-py-117.md
- q14: 4/src-hrono-registry-validation-git-auth-py-179.md
- q15: root.md > 19/src-hrono-paths-py-146.md
- q16: root.md
- q17: root.md
- q18: root.md > 18/src-hrono-export-collapse-py-93.md
- q19: root.md
- q20: root.md
- q21: root.md
- q22: root.md

### noroot (export, `/Users/orest/repos/hrono/.claude/worktrees/E027/.scratch/out/noroot`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 2 | 2 | 1 | 3 | 17051 | 7.8 |
| q02 | shallow | yes | yes | yes | 1 | 1 | 1 | 2 | 15112 | 7.1 |
| q03 | shallow | yes | yes | yes | 2 | 2 | 1 | 4 | 24130 | 11.9 |
| q04 | deep | yes | yes | yes | 1 | - | - | 3 | 22266 | 8.9 |
| q05 | deep | yes | yes | yes | 0 | - | - | 1 | 7547 | 6.0 |
| q06 | deep | yes | yes | yes | 1 | - | - | 3 | 22574 | 9.4 |
| q07 | deep | yes | yes | yes | 1 | - | - | 2 | 9941 | 6.4 |
| q08 | deep | yes | yes | yes | 0 | - | - | 1 | 10349 | 5.2 |
| q09 | deep | yes | yes | yes | 2 | - | - | 4 | 24760 | 9.3 |
| q10 | deep | yes | yes | yes | 2 | 2 | 1 | 4 | 28776 | 11.4 |
| q11 | deep | yes | yes | yes | 1 | - | - | 2 | 11440 | 6.0 |
| q12 | shallow | yes | yes | yes | 2 | 2 | 1 | 4 | 32711 | 9.7 |
| q13 | deep | yes | yes | yes | 2 | 2 | 1 | 5 | 41740 | 12.4 |
| q14 | deep | yes | yes | yes | 1 | 1 | 1 | 2 | 11230 | 7.6 |
| q15 | deep | no | no | yes | 2 | 2 | 1 | 3 | 20215 | 8.3 |
| q16 | deep | yes | yes | yes | 1 | - | - | 2 | 11663 | 6.3 |
| q17 | deep | no | yes | no | 1 | - | - | 3 | 22045 | 7.8 |
| q18 | deep | yes | yes | yes | 2 | 2 | 1 | 3 | 23636 | 8.2 |
| q19 | shallow | yes | yes | yes | 1 | - | - | 3 | 21770 | 9.9 |
| q20 | none | yes | yes | yes | 1 | - | - | 3 | 15234 | 7.7 |
| q21 | none | yes | yes | yes | 1 | - | - | 3 | 15556 | 7.9 |
| q22 | none | yes | yes | yes | 1 | - | - | 3 | 20299 | 6.9 |

Pages opened, in order:

- q01: root.md > 17/src-hrono-tree-commands-py-293.md
- q02: 14/src-hrono-summarize-pool-py-284.md
- q03: root.md > 7/src-hrono-crypto-tokens-py-37.md
- q04: root.md
- q05: none
- q06: root.md
- q07: root.md
- q08: none
- q09: root.md > 2/src-hrono-server-templates-guide-html-231.md
- q10: root.md > 14/src-hrono-summarize-propagate-py-285.md
- q11: root.md
- q12: root.md > 8/src-hrono-ingest-split-constants-py-117.md
- q13: root.md > 8/src-hrono-ingest-split-constants-py-117.md
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
- answered: Recall uses weighted reciprocal rank fusion, with vector weight 0.7, keyword weight 0.3 and k=60, so score = 0.7/(60+vector_rank) + 0.3/(60+keyword_rank). Each term is added only for a leg where the passage qualified, and the union is capped at 10 hits.
- cited: recall-m5-overview-this-group-documents-the-recall-pipeline-13/src-hrono-recall-fusion-py-155.md (repository path: src/hrono/recall/fusion.py)
- tools in order: Read > Grep > Read
- pages opened in order:
  1. `root.md`
  2. `recall-m5-overview-this-group-documents-the-recall-pipeline-13/src-hrono-recall-fusion-py-155.md` (src/hrono/recall/fusion.py)

### noroot / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs in `paths.cli_workdir`, an empty directory hrono owns. The CLI reads the PROJECT MEMORY of its working directory, so this keeps the operator's project context out of the calls, and `--safe-mode` also covers it.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Grep > Read
- pages opened in order:
  1. `root.md`
  2. `m4-text-completion-seam-3/src-hrono-llm-claude-code-py-138.md` (src/hrono/llm/claude_code.py)

### noroot / q17: How many update runs may a chunk wait in the incubator pool before it is forced out?

- expected: 5, five in src/hrono/cluster/incubator.py
- answered: 5 update runs (`MAX_AGE = 5`). A chunk that has waited longer than that is force-assigned out of the pool.
- cited: hronо-clustering-subsystem-overview-6/src-hrono-cluster-incubator-py-19.md
- tools in order: Read > Grep > Grep
- pages opened in order:
  1. `root.md`
