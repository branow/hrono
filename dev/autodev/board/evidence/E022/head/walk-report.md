# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob. 22 questions x 1 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| after-3 | 19/22 | 21/22 | 20/22 | 3.1 | 3.2 | 18/19 | 827013 | 15106 | 10.0 | 1.46 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "The canary word is **PELICAN-7731**, and the one skill name is `graphify` (trigger `/graphify`). Other distinctive names in my context: - **Hook and tool names:** `sensitive-canary` (0.8.1 vendored, 0.8.2 available) and `/update-canary`. - **Plexus repos and apps:** `website-monoreact`, `website-bac"
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "There are no canary words, skill names or memory files. The distinctive names in my instructions are: - **Tool names:** Glob, Grep, Read - **Other identifiers:** - The Claude Agent SDK - The model name "Sonnet 5.5" and its ID `claude-sonnet-5-5` - The user email in the context block, orest.bodnar@te"
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### after-3 (export, `/Users/orest/repos/hrono/.claude/worktrees/E022/.scratch/out/after-3`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 4 | 4 | 1 | 4 | 42747 | 11.0 |
| q02 | shallow | yes | yes | yes | 3 | 3 | 1 | 3 | 22131 | 8.6 |
| q03 | shallow | yes | yes | yes | 4 | 4 | 1 | 5 | 40004 | 13.0 |
| q04 | deep | yes | yes | yes | 7 | 7 | 1 | 9 | 114413 | 17.3 |
| q05 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 33610 | 8.8 |
| q06 | deep | yes | yes | yes | 2 | 2 | 1 | 3 | 25057 | 9.3 |
| q07 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 33611 | 9.8 |
| q08 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 41875 | 9.6 |
| q09 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 42248 | 9.9 |
| q10 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 19805 | 8.5 |
| q11 | deep | yes | yes | yes | 4 | 3 | 1 | 5 | 36381 | 10.2 |
| q12 | shallow | no | yes | no | 2 | - | - | 2 | 19027 | 7.7 |
| q13 | deep | yes | yes | yes | 3 | 3 | 1 | 5 | 42720 | 11.0 |
| q14 | deep | yes | yes | yes | 4 | 4 | 1 | 6 | 70370 | 14.0 |
| q15 | deep | no | no | yes | 2 | 2 | 1 | 2 | 18965 | 8.4 |
| q16 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 18797 | 7.4 |
| q17 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 42988 | 10.3 |
| q18 | deep | no | yes | no | 3 | 3 | 1 | 4 | 35886 | 9.9 |
| q19 | shallow | yes | yes | yes | 4 | 4 | 1 | 4 | 45528 | 10.0 |
| q20 | none | yes | yes | yes | 2 | - | - | 2 | 17282 | 7.7 |
| q21 | none | yes | yes | yes | 3 | - | - | 4 | 37082 | 9.9 |
| q22 | none | yes | yes | yes | 3 | - | - | 3 | 26486 | 8.1 |

Pages opened, in order:

- q01: root.md > 14/brief.md > 15/src-hrono-cli-py-12.md > 14/src-hrono-tree-commands-py-260.md
- q02: root.md > 6/brief.md > 15/readme-md-3.md
- q03: root.md > 10/brief.md > 9/src-hrono-db-migrations-0002-users-sql-44.md > 15/src-hrono-crypto-tokens-py-36.md
- q04: root.md > 2/src-hrono-export-render-py-91.md > 2/brief.md > 14/brief.md > 2/src-hrono-server-templates-export-html-207.md > 14/src-hrono-export-init-py-88.md > 16/src-hrono-export-collapse-py-89.md
- q05: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-149.md
- q06: root.md > 11/src-hrono-recall-fusion-py-149.md
- q07: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-149.md
- q08: root.md > 13/brief.md > 13/src-hrono-cluster-placement-py-25.md
- q09: root.md > 13/brief.md > 13/src-hrono-cluster-repair-py-27.md
- q10: root.md > 12/src-hrono-summarize-propagate-py-253.md
- q11: root.md > 10/src-hrono-server-jobs-py-188.md > 10/src-hrono-jobs-worker-py-129.md > 10/src-hrono-jobs-worker-py-130.md
- q12: root.md > 3/src-hrono-ingest-split-pack-py-114.md
- q13: root.md > 3/src-hrono-ingest-split-pack-py-114.md > 3/src-hrono-ingest-split-constants-py-111.md
- q14: root.md > 4/brief.md > 4/src-hrono-ingest-git-syncer-py-101.md > 5/src-hrono-registry-validation-git-auth-py-170.md
- q15: root.md > 6/src-hrono-llm-claude-code-py-132.md
- q16: root.md > 6/src-hrono-llm-claude-code-py-132.md
- q17: root.md > 13/brief.md > 13/src-hrono-cluster-incubator-py-18.md
- q18: root.md > 14/brief.md > 16/src-hrono-export-collapse-py-89.md
- q19: root.md > 15/src-hrono-cli-py-12.md > 15/brief.md > 15/src-hrono-profile-store-py-143.md
- q20: root.md > 15/readme-md-3.md
- q21: root.md > 15/brief.md > 15/readme-md-3.md
- q22: root.md > 11/brief.md > 15/brief.md

## Failed paths

### after-3 / q12: What is the target size in bytes of a passage, the unit recall injects?

- expected: 800 in src/hrono/ingest/split/constants.py, GLOSSARY.md, CONTRIBUTING.md
- answered: A passage targets about 800 bytes (`PASSAGE_BYTES`, roughly 200 tokens). Sections are about 10 KB.
- cited: root.md, src/hrono/ingest/split/pack.py
- tools in order: Read > Read
- pages opened in order:
  1. `root.md`
  2. `what-this-is-3/src-hrono-ingest-split-pack-py-114.md` (src/hrono/ingest/split/pack.py)

### after-3 / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs in `paths.cli_workdir`, an empty directory owned by hrono, because the CLI reads the PROJECT MEMORY of its working directory. This keeps the operator's project context out of the summarizer calls, as a second safeguard alongside `--safe-mode`.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Read
- pages opened in order:
  1. `root.md`
  2. `llm-and-embedding-call-layer-of-the-hrono-project-m4-summari-6/src-hrono-llm-claude-code-py-132.md` (src/hrono/llm/claude_code.py)

### after-3 / q18: What does the export collapse do with a requested hop limit below 2?

- expected: clamp, raised to 2, at least 2, treated as 2 in src/hrono/export/collapse.py
- answered: A requested hop limit below 2 is clamped to 2, so the export always has at least a root level and a leaf level.
- cited: this-group-condenses-the-modules-of-hrono-a-tool-that-turns--16/src-hrono-export-collapse-py-89.md (repository path: src/hrono/export/collapse.py)
- tools in order: Read > Read > Glob > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-tree-subsystem-14/brief.md`
  3. `this-group-condenses-the-modules-of-hrono-a-tool-that-turns--16/src-hrono-export-collapse-py-89.md` (src/hrono/export/collapse.py)
