# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob. 22 questions x 1 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| after-2 | 20/22 | 21/22 | 21/22 | 3.1 | 3.0 | 19/19 | 854292 | 14700 | 9.6 | 1.49 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "Here are the distinctive items, grouped: - **Canary and skill:** PELICAN-7731 (canary word), graphify (skill, `/graphify`, `~/.claude/skills/graphify/SKILL.md`) - **Hook items:** sensitive-canary (0.8.2 available, 0.8.1 vendored), `/update-canary`, plexus-context - **Plexus repos and systems:** webs"
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "I found no canary words, skill names or memory files. The distinctive names in my instructions are: - **Tools:** Glob, Grep, Read. The prompt also mentions deferred tools, but it doesn't name any. - **Environment:** the working directory `/private/var/folders/fr/c3v2xm9s7gv64p8vhvsfld8w0000gn/T/hron"
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### after-2 (export, `/Users/orest/repos/hrono/.claude/worktrees/E022/.scratch/out/after-2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 3 | 3 | 1 | 3 | 37303 | 9.6 |
| q02 | shallow | yes | yes | yes | 4 | 4 | 1 | 4 | 48513 | 10.1 |
| q03 | shallow | yes | yes | yes | 4 | 2 | 1 | 5 | 29513 | 13.8 |
| q04 | deep | yes | yes | yes | 8 | 8 | 1 | 8 | 151477 | 18.4 |
| q05 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 19135 | 7.1 |
| q06 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 19302 | 8.3 |
| q07 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 37885 | 9.5 |
| q08 | deep | no | yes | no | 3 | 3 | 1 | 4 | 46681 | 9.7 |
| q09 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 21380 | 7.3 |
| q10 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 21770 | 8.6 |
| q11 | deep | yes | yes | yes | 5 | 4 | 1 | 5 | 63342 | 11.8 |
| q12 | shallow | yes | yes | yes | 2 | 2 | 1 | 2 | 19002 | 7.3 |
| q13 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 18960 | 6.7 |
| q14 | deep | yes | yes | yes | 4 | 4 | 1 | 5 | 56367 | 11.8 |
| q15 | deep | no | no | yes | 2 | 2 | 1 | 2 | 20844 | 7.8 |
| q16 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 20666 | 7.0 |
| q17 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 45886 | 10.3 |
| q18 | deep | yes | yes | yes | 4 | 4 | 1 | 4 | 48269 | 9.5 |
| q19 | shallow | yes | yes | yes | 3 | 3 | 1 | 3 | 40210 | 9.0 |
| q20 | none | yes | yes | yes | 3 | - | - | 3 | 25851 | 8.4 |
| q21 | none | yes | yes | yes | 3 | - | - | 4 | 39958 | 9.6 |
| q22 | none | yes | yes | yes | 2 | - | - | 3 | 21978 | 9.0 |

Pages opened, in order:

- q01: root.md > 14/brief.md > 14/src-hrono-tree-commands-py-260.md
- q02: root.md > 6/brief.md > 12/brief.md > 12/src-hrono-summarize-pool-py-252.md
- q03: root.md > 15/src-hrono-auth-users-py-11.md > 9/src-hrono-db-migrations-0002-users-sql-44.md > 15/src-hrono-crypto-tokens-py-36.md
- q04: root.md > 2/brief.md > 2/src-hrono-export-render-py-91.md > 2/src-hrono-server-templates-export-html-207.md > 14/brief.md > 14/src-hrono-export-init-py-88.md > 16/brief.md > 16/src-hrono-export-collapse-py-89.md
- q05: root.md > 11/src-hrono-recall-fusion-py-149.md
- q06: root.md > 11/src-hrono-recall-fusion-py-149.md
- q07: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-149.md
- q08: root.md > 13/brief.md > 13/src-hrono-cluster-placement-py-25.md
- q09: root.md > 13/src-hrono-cluster-repair-py-27.md
- q10: root.md > 12/src-hrono-summarize-propagate-py-253.md
- q11: root.md > 10/src-hrono-server-jobs-py-188.md > 10/brief.md > 10/src-hrono-jobs-worker-py-129.md > 10/src-hrono-jobs-worker-py-130.md
- q12: root.md > 3/src-hrono-ingest-split-constants-py-111.md
- q13: root.md > 3/src-hrono-ingest-split-constants-py-111.md
- q14: root.md > 4/brief.md > 4/src-hrono-ingest-git-syncer-py-101.md > 5/src-hrono-registry-validation-git-auth-py-170.md
- q15: root.md > 6/src-hrono-llm-claude-code-py-132.md
- q16: root.md > 6/src-hrono-llm-claude-code-py-132.md
- q17: root.md > 13/brief.md > 13/src-hrono-cluster-incubator-py-18.md
- q18: root.md > 16/brief.md > 14/brief.md > 16/src-hrono-export-collapse-py-89.md
- q19: root.md > 15/brief.md > 15/src-hrono-profile-store-py-143.md
- q20: root.md > 15/readme-md-3.md > 15/brief.md
- q21: root.md > 15/brief.md > 15/readme-md-3.md
- q22: root.md > 11/brief.md

## Failed paths

### after-2 / q08: What similarity threshold (TAU) decides whether a new section is placed into an existing cluster?

- expected: 0.7 in src/hrono/cluster/placement.py
- answered: TAU = 0.70. A new section joins its best-matching cluster centroid if the similarity is >= 0.70; otherwise it is parked in the incubator.
- cited: reference-for-hrono-a-python-project-that-builds-a-topic-tre-13/src-hrono-cluster-placement-py-25.md (repository path: src/hrono/cluster/placement.py)
- tools in order: Read > Read > Glob > Read
- pages opened in order:
  1. `root.md`
  2. `reference-for-hrono-a-python-project-that-builds-a-topic-tre-13/brief.md`
  3. `reference-for-hrono-a-python-project-that-builds-a-topic-tre-13/src-hrono-cluster-placement-py-25.md` (src/hrono/cluster/placement.py)

### after-2 / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs `claude` with `cwd` set to `paths.cli_workdir`, an empty directory owned by hrono. The CLI reads the project memory of its working directory, so this keeps a user's project memory out of the calls, as a second lock alongside `--safe-mode`.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Read
- pages opened in order:
  1. `root.md`
  2. `llm-and-embedding-call-layer-of-the-hrono-project-m4-summari-6/src-hrono-llm-claude-code-py-132.md` (src/hrono/llm/claude_code.py)
