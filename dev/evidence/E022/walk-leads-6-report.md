# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob. 22 questions x 1 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| after-6 | 19/22 | 21/22 | 20/22 | 2.9 | 2.7 | 19/19 | 932470 | 14110 | 9.3 | 1.64 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "Distinctive items beyond this message: - **Canary word:** PELICAN-7731 (from the project CLAUDE.md; I'm to mention it whenever asked) - **Skill:** graphify (`/graphify`, invoked via the Skill tool) - **Hook/package:** sensitive-canary (0.8.1 vendored, 0.8.2 available), and the `/update-canary` comma"
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "There are no canary words, skill names or memory files in my context. These are the distinctive names it does contain: - **Tools:** Glob, Grep, Read. A deferred-tools mechanism is also mentioned, but no specific names are given. - **Identity and model:** Claude Agent SDK, Sonnet 5.5, claude-sonnet-5"
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### after-6 (export, `/Users/orest/repos/hrono/.claude/worktrees/E022/.scratch/out/after-6`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 3 | 3 | 1 | 3 | 30919 | 8.3 |
| q02 | shallow | yes | yes | yes | 4 | 4 | 1 | 5 | 51148 | 10.6 |
| q03 | shallow | yes | yes | yes | 4 | 2 | 1 | 5 | 51940 | 14.6 |
| q04 | deep | no | yes | no | 4 | 4 | 1 | 5 | 69243 | 11.5 |
| q05 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 24825 | 6.6 |
| q06 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 24972 | 8.1 |
| q07 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 46423 | 9.9 |
| q08 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 42216 | 10.1 |
| q09 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 27082 | 7.1 |
| q10 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 27387 | 7.7 |
| q11 | deep | no | yes | no | 4 | 2 | 1 | 4 | 70935 | 10.6 |
| q12 | shallow | yes | yes | yes | 2 | 2 | 1 | 2 | 24645 | 7.0 |
| q13 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 24715 | 6.7 |
| q14 | deep | yes | yes | yes | 4 | 4 | 1 | 5 | 67799 | 11.4 |
| q15 | deep | no | no | yes | 2 | 2 | 1 | 2 | 26499 | 7.7 |
| q16 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 26409 | 7.2 |
| q17 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 53851 | 9.9 |
| q18 | deep | yes | yes | yes | 5 | 5 | 1 | 7 | 91879 | 14.8 |
| q19 | shallow | yes | yes | yes | 3 | 3 | 1 | 3 | 48746 | 8.7 |
| q20 | none | yes | yes | yes | 2 | - | - | 2 | 24864 | 7.2 |
| q21 | none | yes | yes | yes | 3 | - | - | 4 | 48471 | 10.4 |
| q22 | none | yes | yes | yes | 2 | - | - | 2 | 27502 | 7.9 |

Pages opened, in order:

- q01: root.md > 14/brief.md > 14/src-hrono-tree-commands-py-260.md
- q02: root.md > 6/brief.md > 12/brief.md > 15/readme-md-3.md
- q03: root.md > 15/src-hrono-auth-users-py-11.md > 9/src-hrono-db-migrations-0001-keys-sql-43.md > 15/src-hrono-crypto-tokens-py-36.md
- q04: root.md > 2/src-hrono-export-render-py-91.md > 14/brief.md > 16/src-hrono-export-collapse-py-89.md
- q05: root.md > 11/src-hrono-recall-fusion-py-149.md
- q06: root.md > 11/src-hrono-recall-fusion-py-149.md
- q07: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-149.md
- q08: root.md > 13/src-hrono-cluster-recipe-py-26.md > 13/src-hrono-cluster-placement-py-25.md
- q09: root.md > 13/src-hrono-cluster-repair-py-27.md
- q10: root.md > 12/src-hrono-summarize-propagate-py-253.md
- q11: root.md > 10/src-hrono-jobs-worker-py-130.md > 10/brief.md > 10/src-hrono-jobs-worker-py-129.md
- q12: root.md > 3/src-hrono-ingest-split-constants-py-111.md
- q13: root.md > 3/src-hrono-ingest-split-constants-py-111.md
- q14: root.md > 4/brief.md > 4/src-hrono-ingest-git-syncer-py-101.md > 5/src-hrono-registry-validation-git-auth-py-170.md
- q15: root.md > 6/src-hrono-llm-claude-code-py-132.md
- q16: root.md > 6/src-hrono-llm-claude-code-py-132.md
- q17: root.md > 13/brief.md > 13/src-hrono-cluster-incubator-py-18.md
- q18: root.md > 14/brief.md > 14/src-hrono-export-init-py-88.md > 2/brief.md > 16/src-hrono-export-collapse-py-89.md
- q19: root.md > 15/brief.md > 15/src-hrono-profile-store-py-143.md
- q20: root.md > 15/readme-md-3.md
- q21: root.md > 15/brief.md > 15/readme-md-3.md
- q22: root.md > 11/brief.md

## Failed paths

### after-6 / q04: In the export, how many entries is one index page budgeted to list?

- expected: 40 in src/hrono/export/collapse.py
- answered: One index page is budgeted to list 40 entries (`WIDTH = 40`), which is about 10 KB, the size of one section.
- cited: this-group-condenses-the-modules-of-hrono-a-tool-that-turns--16/src-hrono-export-collapse-py-89.md (repository path: src/hrono/export/collapse.py)
- tools in order: Read > Read > Read > Glob > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-export-renderer-and-its-web-ui-templates-2/src-hrono-export-render-py-91.md` (src/hrono/export/render.py)
  3. `hrono-tree-subsystem-14/brief.md`
  4. `this-group-condenses-the-modules-of-hrono-a-tool-that-turns--16/src-hrono-export-collapse-py-89.md` (src/hrono/export/collapse.py)

### after-6 / q11: How often, in seconds, does the job worker write its heartbeat?

- expected: 5 in src/hrono/jobs/worker.py
- answered: Every 5 seconds (`HEARTBEAT_INTERVAL = 5.0`).
- cited: src/hrono/jobs/worker.py (section file `hrono-backend-s-storage-job-execution-and-operator-layers-10/src-hrono-jobs-worker-py-129.md`)
- tools in order: Read > Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-backend-s-storage-job-execution-and-operator-layers-10/src-hrono-jobs-worker-py-130.md` (src/hrono/jobs/worker.py)
  3. `hrono-backend-s-storage-job-execution-and-operator-layers-10/brief.md`
  4. `hrono-backend-s-storage-job-execution-and-operator-layers-10/src-hrono-jobs-worker-py-129.md` (src/hrono/jobs/worker.py)

### after-6 / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs in `paths.cli_workdir`, an empty directory hrono owns, because the CLI reads the PROJECT MEMORY of its working directory and this keeps that context out of summarization calls. `--safe-mode` also covers this, and the empty directory is a second lock.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Read
- pages opened in order:
  1. `root.md`
  2. `llm-and-embedding-call-layer-of-the-hrono-project-m4-summari-6/src-hrono-llm-claude-code-py-132.md` (src/hrono/llm/claude_code.py)
