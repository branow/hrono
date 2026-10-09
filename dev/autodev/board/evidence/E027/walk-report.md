# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob. 22 questions x 2 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| head | 18/22 | 20/22 | 19/22 | 3.2 | 3.2 | 18/19 | 871310 | 15074 | 10.6 | 1.45 |
| noroot | 19/22 | 19/22 | 21/22 | 3.5 | 3.4 | 18/19 | 832892 | 15783 | 10.5 | 1.43 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "Distinctive items beyond your message: - **Canary word:** PELICAN-7731, from the project CLAUDE.md, which says to mention it whenever asked. - **Skill:** graphify (`/graphify`), from your global CLAUDE.md. - **Hooks and commands:** sensitive-canary (0.8.2 available, 0.8.1 vendored) and `/update-cana"
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "Here are the distinctive names in my instructions and context: - **Tools:** Glob, Grep, Read - **Other names:** Claude Agent SDK, Sonnet 5.5 (`claude-sonnet-5-5`), ripgrep (named in the Grep description) I found no canary words, skill names or memory-file entries."
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### head (export, `/Users/orest/repos/hrono/.claude/worktrees/E027/.scratch/out/base-l2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 3 | 3 | 1 | 4 | 32527 | 10.5 |
| q02 | shallow | yes | yes | yes | 4 | 4 | 1 | 4 | 42756 | 9.4 |
| q03 | shallow | yes | yes | yes | 3 | 2 | 1 | 4 | 35467 | 13.3 |
| q04 | deep | yes | yes | yes | 3 | 2 | 1 | 4 | 25824 | 10.0 |
| q05 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 30650 | 9.1 |
| q06 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 32033 | 10.6 |
| q07 | deep | no | yes | no | 3 | 3 | 1 | 3 | 30813 | 11.9 |
| q08 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 36662 | 10.2 |
| q09 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 39732 | 9.6 |
| q10 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 37563 | 10.0 |
| q11 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 35716 | 8.9 |
| q12 | shallow | yes | yes | yes | 4 | 4 | 1 | 6 | 60214 | 13.8 |
| q13 | deep | no | yes | no | 4 | 4 | 1 | 6 | 60448 | 13.4 |
| q14 | deep | yes | yes | yes | 5 | 5 | 1 | 6 | 78211 | 14.1 |
| q15 | deep | no | no | yes | 2 | 2 | 1 | 2 | 17674 | 7.9 |
| q16 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 17593 | 8.3 |
| q17 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 39950 | 10.8 |
| q18 | deep | no | no | no | 4 | - | - | 4 | 41781 | 10.9 |
| q19 | shallow | yes | yes | yes | 5 | 5 | 1 | 6 | 109336 | 13.9 |
| q20 | none | yes | yes | yes | 2 | - | - | 2 | 15047 | 7.8 |
| q21 | none | yes | yes | yes | 3 | - | - | 4 | 32070 | 10.2 |
| q22 | none | yes | yes | yes | 2 | - | - | 2 | 19243 | 7.6 |

Pages opened, in order:

- q01: root.md > 17/brief.md > 17/src-hrono-tree-commands-py-293.md
- q02: root.md > 3/brief.md > 14/brief.md > 14/src-hrono-summarize-pool-py-284.md
- q03: root.md > 20/src-hrono-auth-users-py-12.md > 7/src-hrono-crypto-tokens-py-37.md
- q04: root.md > 18/src-hrono-export-collapse-py-93.md > 18/src-hrono-export-init-py-91.md
- q05: root.md > 13/brief.md > 13/src-hrono-recall-fusion-py-155.md
- q06: root.md > 13/brief.md > 13/src-hrono-recall-fusion-py-155.md
- q07: root.md > 13/brief.md > 13/src-hrono-recall-fusion-py-155.md
- q08: root.md > 6/brief.md > 6/src-hrono-cluster-placement-py-26.md
- q09: root.md > 6/brief.md > 6/src-hrono-cluster-repair-py-28.md
- q10: root.md > 14/brief.md > 14/src-hrono-summarize-propagate-py-285.md
- q11: root.md > 15/brief.md > 15/src-hrono-jobs-worker-py-135.md
- q12: root.md > 9/brief.md > 9/src-hrono-ingest-split-pack-py-120.md > 8/src-hrono-ingest-split-constants-py-117.md
- q13: root.md > 9/brief.md > 9/src-hrono-ingest-split-pack-py-120.md > 8/src-hrono-ingest-split-constants-py-117.md
- q14: root.md > 8/brief.md > 8/src-hrono-ingest-git-syncer-py-106.md > 8/src-hrono-ingest-remote-head-py-114.md > 4/src-hrono-registry-validation-git-auth-py-179.md
- q15: root.md > 3/src-hrono-llm-claude-code-py-138.md
- q16: root.md > 3/src-hrono-llm-claude-code-py-138.md
- q17: root.md > 6/brief.md > 6/src-hrono-cluster-incubator-py-19.md
- q18: root.md > 17/brief.md > 16/brief.md > 16/src-hrono-server-trees-py-246.md
- q19: root.md > 18/brief.md > 20/brief.md > 20/src-hrono-client-http-py-15.md > 19/src-hrono-profile-store-py-149.md
- q20: root.md > 18/pyproject-toml-5.md
- q21: root.md > 19/brief.md > 19/readme-md-3.md
- q22: root.md > 20/brief.md

### noroot (export, `/Users/orest/repos/hrono/.claude/worktrees/E027/.scratch/out/noroot`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 3 | 3 | 1 | 4 | 29296 | 9.6 |
| q02 | shallow | yes | yes | yes | 4 | 4 | 1 | 4 | 45897 | 10.1 |
| q03 | shallow | no | no | yes | 5 | 4 | 1 | 5 | 43736 | 13.0 |
| q04 | deep | yes | yes | yes | 3 | 2 | 1 | 5 | 21900 | 10.0 |
| q05 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 26591 | 9.3 |
| q06 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 26768 | 10.3 |
| q07 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 26721 | 10.4 |
| q08 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 35223 | 9.1 |
| q09 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 35664 | 9.3 |
| q10 | deep | yes | yes | yes | 4 | 4 | 1 | 4 | 40980 | 11.5 |
| q11 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 31537 | 8.7 |
| q12 | shallow | yes | yes | yes | 4 | 4 | 1 | 6 | 46673 | 14.2 |
| q13 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 27078 | 9.6 |
| q14 | deep | yes | yes | yes | 5 | 5 | 1 | 6 | 71353 | 13.7 |
| q15 | deep | no | no | yes | 3 | 3 | 1 | 3 | 26801 | 10.1 |
| q16 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 26607 | 8.8 |
| q17 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 35742 | 9.8 |
| q18 | deep | no | no | no | 5 | - | - | 5 | 51812 | 12.4 |
| q19 | shallow | yes | yes | yes | 6 | 5 | 1 | 7 | 128131 | 16.0 |
| q20 | none | yes | yes | yes | 3 | - | - | 3 | 22588 | 9.1 |
| q21 | none | yes | yes | yes | 2 | - | - | 3 | 15383 | 8.4 |
| q22 | none | yes | yes | yes | 2 | - | - | 2 | 16411 | 6.5 |

Pages opened, in order:

- q01: root.md > 17/brief.md > 17/src-hrono-tree-commands-py-293.md
- q02: root.md > 14/brief.md > 15/brief.md > 14/src-hrono-summarize-pool-py-284.md
- q03: root.md > 20/brief.md > 12/brief.md > 20/src-hrono-auth-users-py-12.md > 12/src-hrono-db-migrations-0002-users-sql-45.md
- q04: root.md > 18/src-hrono-export-collapse-py-93.md > 18/src-hrono-export-init-py-91.md
- q05: root.md > 13/brief.md > 13/src-hrono-recall-fusion-py-155.md
- q06: root.md > 13/brief.md > 13/src-hrono-recall-fusion-py-155.md
- q07: root.md > 13/brief.md > 13/src-hrono-recall-fusion-py-155.md
- q08: root.md > 6/brief.md > 6/src-hrono-cluster-placement-py-26.md
- q09: root.md > 6/brief.md > 6/src-hrono-cluster-repair-py-28.md
- q10: root.md > 14/brief.md > 3/brief.md > 14/src-hrono-summarize-propagate-py-285.md
- q11: root.md > 15/brief.md > 15/src-hrono-jobs-worker-py-135.md
- q12: root.md > 9/brief.md > 9/src-hrono-ingest-split-pack-py-120.md > 8/src-hrono-ingest-split-constants-py-117.md
- q13: root.md > 9/brief.md > 8/src-hrono-ingest-split-constants-py-117.md
- q14: root.md > 8/brief.md > 8/src-hrono-ingest-git-syncer-py-106.md > 8/src-hrono-ingest-remote-head-py-114.md > 4/src-hrono-registry-validation-git-auth-py-179.md
- q15: root.md > 3/brief.md > 3/src-hrono-llm-claude-code-py-138.md
- q16: root.md > 3/brief.md > 3/src-hrono-llm-claude-code-py-138.md
- q17: root.md > 6/brief.md > 6/src-hrono-cluster-incubator-py-19.md
- q18: root.md > 17/brief.md > 16/brief.md > 17/src-hrono-server-trees-py-246.md > 16/src-hrono-server-trees-py-246.md
- q19: root.md > 20/brief.md > 18/brief.md > 20/src-hrono-client-http-py-15.md > 19/src-hrono-profile-store-py-149.md > 19/src-hrono-profile-store-py-149.md
- q20: root.md > 18/brief.md > 18/pyproject-toml-5.md
- q21: root.md > 19/brief.md
- q22: root.md > 20/brief.md

## Failed paths

### head / q07: What is the largest share of the recall window that passages from one document may take?

- expected: 0.4, 40%, 40 % in src/hrono/recall/fusion.py
- answered: Each document's reserved share of the 10-hit window is 40% (4 hits). This is a soft reserve rather than a hard cap, so one document can exceed it, up to all 10 slots, only if no other document has a qualifying hit left.
- cited: recall-m5-overview-this-group-documents-the-recall-pipeline-13/src-hrono-recall-fusion-py-155.md (repository path: src/hrono/recall/fusion.py)
- tools in order: Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `recall-m5-overview-this-group-documents-the-recall-pipeline-13/brief.md`
  3. `recall-m5-overview-this-group-documents-the-recall-pipeline-13/src-hrono-recall-fusion-py-155.md` (src/hrono/recall/fusion.py)

### head / q13: What section size budget, in bytes, applies to files in the data category (as opposed to code and docs)?

- expected: 2048, 2 kb, 2kb in src/hrono/ingest/split/constants.py, GLOSSARY.md
- answered: The data category's section size budget is 2048 bytes (2 KB), versus 10240 bytes (10 KB) for code and docs.
- cited: hrono-a-document-ingestion-and-indexing-system-8/src-hrono-ingest-split-constants-py-117.md (repository path: src/hrono/ingest/split/constants.py)
- tools in order: Read > Read > Read > Glob > Glob > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-ingest-split-package-9/brief.md`
  3. `hrono-ingest-split-package-9/src-hrono-ingest-split-pack-py-120.md` (src/hrono/ingest/split/pack.py)
  4. `hrono-a-document-ingestion-and-indexing-system-8/src-hrono-ingest-split-constants-py-117.md` (src/hrono/ingest/split/constants.py)

### head / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs from `paths.cli_workdir`, an empty directory hrono owns, because the CLI reads the project memory of its working directory. Running from that directory keeps the operator's project context out of the call, as a second lock alongside `--safe-mode`.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Read
- pages opened in order:
  1. `root.md`
  2. `m4-text-completion-seam-3/src-hrono-llm-claude-code-py-138.md` (src/hrono/llm/claude_code.py)

### head / q18: What does the export collapse do with a requested hop limit below 2?

- expected: clamp, raised to 2, at least 2, treated as 2 in src/hrono/export/collapse.py
- answered: It silently raises `levels` to 2 and returns a 2-level export, with no error.
- cited: src/hrono/server/trees.py
- tools in order: Read > Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-s-tree-subsystem-how-trees-are-scoped-to-sources-built-17/brief.md`
  3. `python-sqlite-backend-16/brief.md`
  4. `python-sqlite-backend-16/src-hrono-server-trees-py-246.md` (src/hrono/server/trees.py)

### noroot / q03: How does hrono store a user's API token in the database?

- expected: sha-256, sha256 in src/hrono/crypto/tokens.py, src/hrono/auth/users.py
- answered: hrono stores only a one-way hash of the token, in the unique `token_hash` column of the `users` table. `create_user` and `reset_token` write `hash_token(token)`, the raw token is returned once and never kept, and `authenticate` hashes the presented token and compares it to `token_hash`.
- cited: src/hrono/auth/users.py, src/hrono/db/migrations/0002_users.sql
- tools in order: Read > Read > Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-server-and-its-clients-20/brief.md`
  3. `document-indexing-and-summarization-system-hrono-12/brief.md`
  4. `hrono-server-and-its-clients-20/src-hrono-auth-users-py-12.md` (src/hrono/auth/users.py)
  5. `document-indexing-and-summarization-system-hrono-12/src-hrono-db-migrations-0002-users-sql-45.md` (src/hrono/db/migrations/0002_users.sql)

### noroot / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs in `paths.cli_workdir`, an empty directory hrono owns, because the CLI reads the PROJECT MEMORY of its working directory and would otherwise load the wrong one.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `m4-text-completion-seam-3/brief.md`
  3. `m4-text-completion-seam-3/src-hrono-llm-claude-code-py-138.md` (src/hrono/llm/claude_code.py)

### noroot / q18: What does the export collapse do with a requested hop limit below 2?

- expected: clamp, raised to 2, at least 2, treated as 2 in src/hrono/export/collapse.py
- answered: A `levels` (hop limit) below 2 is floored to 2, so the export has 2 levels and no error is raised.
- cited: src/hrono/server/trees.py
- tools in order: Read > Read > Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-s-tree-subsystem-how-trees-are-scoped-to-sources-built-17/brief.md`
  3. `python-sqlite-backend-16/brief.md`
  4. `hrono-s-tree-subsystem-how-trees-are-scoped-to-sources-built-17/src-hrono-server-trees-py-246.md`
  5. `python-sqlite-backend-16/src-hrono-server-trees-py-246.md` (src/hrono/server/trees.py)
