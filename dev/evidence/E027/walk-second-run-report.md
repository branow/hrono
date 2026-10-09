# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob. 22 questions x 2 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| head | 17/22 | 21/22 | 18/22 | 3.3 | 3.4 | 19/19 | 921701 | 15574 | 10.3 | 1.51 |
| noroot | 18/22 | 19/22 | 20/22 | 3.7 | 3.7 | 18/19 | 961432 | 16751 | 11.0 | 1.57 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "The canary word is **PELICAN-7731**, from the project CLAUDE.md. The skill is `graphify` (trigger `/graphify`), from your global CLAUDE.md. Other distinctive names from hooks and context: - **Hook:** sensitive-canary (0.8.2 available, 0.8.1 vendored) and the `/update-canary` command. - **Plexus repo"
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "There are no canary words, skill names or memory files. The distinctive names in my instructions are: - **Tools:** Glob, Grep, Read. The prompt also says some deferred tools exist, but it doesn't name any. - **Context key:** userEmail, whose value is [email redacted]. - **Environment:** - The"
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### head (export, `/Users/orest/repos/hrono/.claude/worktrees/E027/.scratch/out/base-l2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 3 | 3 | 1 | 4 | 33434 | 9.6 |
| q02 | shallow | yes | yes | yes | 4 | 4 | 1 | 4 | 42804 | 9.5 |
| q03 | shallow | yes | yes | yes | 3 | 2 | 1 | 4 | 35478 | 13.2 |
| q04 | deep | yes | yes | yes | 4 | 4 | 1 | 4 | 52573 | 10.6 |
| q05 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 30664 | 9.3 |
| q06 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 30793 | 9.8 |
| q07 | deep | no | yes | no | 3 | 3 | 1 | 3 | 30735 | 9.5 |
| q08 | deep | no | yes | no | 3 | 3 | 1 | 3 | 39361 | 9.6 |
| q09 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 39735 | 8.9 |
| q10 | deep | no | yes | no | 3 | 3 | 1 | 3 | 37612 | 10.3 |
| q11 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 35715 | 8.9 |
| q12 | shallow | yes | yes | yes | 5 | 5 | 1 | 6 | 61148 | 13.0 |
| q13 | deep | yes | yes | yes | 6 | 6 | 1 | 6 | 80510 | 13.8 |
| q14 | deep | yes | yes | yes | 5 | 5 | 1 | 6 | 78163 | 13.9 |
| q15 | deep | no | no | yes | 2 | 2 | 1 | 2 | 17711 | 7.6 |
| q16 | deep | yes | yes | yes | 2 | 2 | 1 | 2 | 17560 | 7.0 |
| q17 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 37487 | 10.8 |
| q18 | deep | no | yes | no | 2 | 2 | 1 | 3 | 25210 | 9.4 |
| q19 | shallow | yes | yes | yes | 5 | 5 | 1 | 6 | 109453 | 13.5 |
| q20 | none | yes | yes | yes | 2 | - | - | 2 | 15010 | 7.9 |
| q21 | none | yes | yes | yes | 3 | - | - | 4 | 35918 | 9.9 |
| q22 | none | yes | yes | yes | 3 | - | - | 3 | 34627 | 9.6 |

Pages opened, in order:

- q01: root.md > 17/brief.md > 17/src-hrono-tree-commands-py-293.md
- q02: root.md > 14/brief.md > 3/brief.md > 14/src-hrono-summarize-pool-py-284.md
- q03: root.md > 20/src-hrono-auth-users-py-12.md > 7/src-hrono-crypto-tokens-py-37.md
- q04: root.md > 20/brief.md > 18/brief.md > 18/src-hrono-export-collapse-py-93.md
- q05: root.md > 13/brief.md > 13/src-hrono-recall-fusion-py-155.md
- q06: root.md > 13/brief.md > 13/src-hrono-recall-fusion-py-155.md
- q07: root.md > 13/brief.md > 13/src-hrono-recall-fusion-py-155.md
- q08: root.md > 6/brief.md > 6/src-hrono-cluster-placement-py-26.md
- q09: root.md > 6/brief.md > 6/src-hrono-cluster-repair-py-28.md
- q10: root.md > 14/brief.md > 14/src-hrono-summarize-propagate-py-285.md
- q11: root.md > 15/brief.md > 15/src-hrono-jobs-worker-py-135.md
- q12: root.md > 9/brief.md > 9/src-hrono-ingest-split-pack-py-120.md > 9/src-hrono-ingest-split-init-py-115.md > 8/src-hrono-ingest-split-constants-py-117.md
- q13: root.md > 9/brief.md > 9/src-hrono-ingest-split-pack-py-120.md > 9/src-hrono-ingest-split-init-py-115.md > 8/brief.md > 8/src-hrono-ingest-split-constants-py-117.md
- q14: root.md > 8/brief.md > 8/src-hrono-ingest-git-syncer-py-106.md > 8/src-hrono-ingest-remote-head-py-114.md > 4/src-hrono-registry-validation-git-auth-py-179.md
- q15: root.md > 3/src-hrono-llm-claude-code-py-138.md
- q16: root.md > 3/src-hrono-llm-claude-code-py-138.md
- q17: root.md > 6/brief.md > 6/src-hrono-cluster-incubator-py-19.md
- q18: root.md > 18/src-hrono-export-collapse-py-93.md
- q19: root.md > 20/brief.md > 18/brief.md > 20/src-hrono-client-http-py-15.md > 19/src-hrono-profile-store-py-149.md
- q20: root.md > 18/pyproject-toml-5.md
- q21: root.md > 19/brief.md > 19/readme-md-3.md
- q22: root.md > 20/brief.md > 19/readme-md-3.md

### noroot (export, `/Users/orest/repos/hrono/.claude/worktrees/E027/.scratch/out/noroot`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 3 | 3 | 1 | 4 | 29290 | 9.6 |
| q02 | shallow | yes | yes | yes | 4 | 4 | 1 | 4 | 45862 | 9.7 |
| q03 | shallow | no | no | yes | 5 | 4 | 1 | 5 | 43762 | 12.8 |
| q04 | deep | no | yes | no | 5 | 5 | 1 | 6 | 39492 | 13.0 |
| q05 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 26564 | 9.3 |
| q06 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 26716 | 10.3 |
| q07 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 26624 | 10.3 |
| q08 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 35210 | 9.1 |
| q09 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 35599 | 8.8 |
| q10 | deep | yes | yes | yes | 4 | 4 | 1 | 4 | 41102 | 11.6 |
| q11 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 31638 | 9.1 |
| q12 | shallow | yes | yes | yes | 5 | 5 | 1 | 6 | 70789 | 12.5 |
| q13 | deep | yes | yes | yes | 4 | 4 | 1 | 4 | 43850 | 16.1 |
| q14 | deep | yes | yes | yes | 5 | 5 | 1 | 6 | 71374 | 13.2 |
| q15 | deep | no | no | yes | 3 | 3 | 1 | 3 | 26829 | 9.8 |
| q16 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 26574 | 8.1 |
| q17 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 32766 | 9.4 |
| q18 | deep | no | no | no | 8 | - | - | 9 | 149876 | 21.7 |
| q19 | shallow | yes | yes | yes | 5 | 5 | 1 | 6 | 100788 | 12.2 |
| q20 | none | yes | yes | yes | 2 | - | - | 2 | 12237 | 7.5 |
| q21 | none | yes | yes | yes | 3 | - | - | 4 | 28045 | 9.6 |
| q22 | none | yes | yes | yes | 2 | - | - | 2 | 16445 | 7.3 |

Pages opened, in order:

- q01: root.md > 17/brief.md > 17/src-hrono-tree-commands-py-293.md
- q02: root.md > 14/brief.md > 15/brief.md > 14/src-hrono-summarize-pool-py-284.md
- q03: root.md > 20/brief.md > 12/brief.md > 20/src-hrono-auth-users-py-12.md > 12/src-hrono-db-migrations-0002-users-sql-45.md
- q04: root.md > 18/src-hrono-export-init-py-91.md > 18/src-hrono-export-render-py-95.md > 18/src-hrono-export-render-py-96.md > 18/src-hrono-export-collapse-py-93.md
- q05: root.md > 13/brief.md > 13/src-hrono-recall-fusion-py-155.md
- q06: root.md > 13/brief.md > 13/src-hrono-recall-fusion-py-155.md
- q07: root.md > 13/brief.md > 13/src-hrono-recall-fusion-py-155.md
- q08: root.md > 6/brief.md > 6/src-hrono-cluster-placement-py-26.md
- q09: root.md > 6/brief.md > 6/src-hrono-cluster-repair-py-28.md
- q10: root.md > 14/brief.md > 3/brief.md > 14/src-hrono-summarize-propagate-py-285.md
- q11: root.md > 15/brief.md > 15/src-hrono-jobs-worker-py-135.md
- q12: root.md > 9/brief.md > 13/brief.md > 9/src-hrono-ingest-split-pack-py-120.md > 8/src-hrono-ingest-split-constants-py-117.md
- q13: root.md > 9/brief.md > 8/brief.md > 8/src-hrono-ingest-split-constants-py-117.md
- q14: root.md > 8/brief.md > 8/src-hrono-ingest-git-syncer-py-106.md > 8/src-hrono-ingest-remote-head-py-114.md > 4/src-hrono-registry-validation-git-auth-py-179.md
- q15: root.md > 3/brief.md > 3/src-hrono-llm-claude-code-py-138.md
- q16: root.md > 3/brief.md > 3/src-hrono-llm-claude-code-py-138.md
- q17: root.md > 6/brief.md > 6/src-hrono-cluster-incubator-py-19.md
- q18: root.md > 17/brief.md > 13/brief.md > 17/src-hrono-tree-commands-py-293.md > 17/src-hrono-tree-init-py-291.md > 14/brief.md > 16/brief.md > 16/src-hrono-server-trees-py-246.md
- q19: root.md > 20/brief.md > 18/brief.md > 20/src-hrono-client-http-py-15.md > 19/src-hrono-profile-store-py-149.md
- q20: root.md > 18/pyproject-toml-5.md
- q21: root.md > 19/brief.md > 19/readme-md-3.md
- q22: root.md > 20/brief.md

## Failed paths

### head / q07: What is the largest share of the recall window that passages from one document may take?

- expected: 0.4, 40%, 40 % in src/hrono/recall/fusion.py
- answered: One document's passages are held to 40% of the 10-hit recall window (4 hits), but this is a reserve, not a hard cap. A document can exceed it only when no other document has a qualifying hit left to fill the slots.
- cited: recall-m5-overview-this-group-documents-the-recall-pipeline-13/src-hrono-recall-fusion-py-155.md (repository path: src/hrono/recall/fusion.py)
- tools in order: Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `recall-m5-overview-this-group-documents-the-recall-pipeline-13/brief.md`
  3. `recall-m5-overview-this-group-documents-the-recall-pipeline-13/src-hrono-recall-fusion-py-155.md` (src/hrono/recall/fusion.py)

### head / q08: What similarity threshold (TAU) decides whether a new section is placed into an existing cluster?

- expected: 0.7 in src/hrono/cluster/placement.py
- answered: TAU = 0.70. A new section joins an existing cluster if its best centroid similarity (dot product) is at least 0.70, and otherwise it is parked in the incubator.
- cited: hrono-clustering-subsystem-overview-6/src-hrono-cluster-placement-py-26.md (repository path: src/hrono/cluster/placement.py)
- tools in order: Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-clustering-subsystem-overview-6/brief.md`
  3. `hrono-clustering-subsystem-overview-6/src-hrono-cluster-placement-py-26.md` (src/hrono/cluster/placement.py)

### head / q10: When a changed leaf is propagated upward, how many judge votes are asked for, and how is the verdict decided?

- expected: majority, median in src/hrono/summarize/propagate.py
- answered: Each changed leaf gets a best-of-3 judge panel (BEST_OF=3), and each member is re-asked once if its reply is unparseable. The verdict is the median of the valid votes, ranked none < minor < major, and it is None if every member abstains.
- cited: summarisation-pipeline-of-the-hrono-codebase-14/src-hrono-summarize-propagate-py-285.md (repository path: src/hrono/summarize/propagate.py)
- tools in order: Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `summarisation-pipeline-of-the-hrono-codebase-14/brief.md`
  3. `summarisation-pipeline-of-the-hrono-codebase-14/src-hrono-summarize-propagate-py-285.md` (src/hrono/summarize/propagate.py)

### head / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs from `paths.cli_workdir`, an empty directory hrono owns. The CLI reads the PROJECT MEMORY of its working directory, so this keeps any project's memory out of the call. `--safe-mode` also covers this, and the empty directory is a second lock.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Read
- pages opened in order:
  1. `root.md`
  2. `m4-text-completion-seam-3/src-hrono-llm-claude-code-py-138.md` (src/hrono/llm/claude_code.py)

### head / q18: What does the export collapse do with a requested hop limit below 2?

- expected: clamp, raised to 2, at least 2, treated as 2 in src/hrono/export/collapse.py
- answered: A `levels` value below 2 is clamped to 2 (`levels = max(2, levels)`), so the export always has at least a root level and a leaf level.
- cited: hrono-v0-1-0-glossary-dependencies-and-server-cli-internals-18/src-hrono-export-collapse-py-93.md (repository path: src/hrono/export/collapse.py)
- tools in order: Read > Glob > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-v0-1-0-glossary-dependencies-and-server-cli-internals-18/src-hrono-export-collapse-py-93.md` (src/hrono/export/collapse.py)

### noroot / q03: How does hrono store a user's API token in the database?

- expected: sha-256, sha256 in src/hrono/crypto/tokens.py, src/hrono/auth/users.py
- answered: hrono stores only a one-way hash of the token, in the `users.token_hash` column (TEXT NOT NULL UNIQUE). The raw token is returned once at creation or reissue and is never stored. Authentication hashes the presented token and looks up the matching `token_hash`.
- cited: src/hrono/auth/users.py, src/hrono/db/migrations/0002_users.sql
- tools in order: Read > Read > Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-server-and-its-clients-20/brief.md`
  3. `document-indexing-and-summarization-system-hrono-12/brief.md`
  4. `hrono-server-and-its-clients-20/src-hrono-auth-users-py-12.md` (src/hrono/auth/users.py)
  5. `document-indexing-and-summarization-system-hrono-12/src-hrono-db-migrations-0002-users-sql-45.md` (src/hrono/db/migrations/0002_users.sql)

### noroot / q04: In the export, how many entries is one index page budgeted to list?

- expected: 40 in src/hrono/export/collapse.py
- answered: One index page is budgeted to list 40 entries (`WIDTH = 40`), which comes to about 10 KB, the size of one section.
- cited: hrono-v0-1-0-glossary-dependencies-and-server-cli-internals-18/src-hrono-export-collapse-py-93.md (repository path: src/hrono/export/collapse.py)
- tools in order: Read > Glob > Read > Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-v0-1-0-glossary-dependencies-and-server-cli-internals-18/src-hrono-export-init-py-91.md` (src/hrono/export/__init__.py)
  3. `hrono-v0-1-0-glossary-dependencies-and-server-cli-internals-18/src-hrono-export-render-py-95.md` (src/hrono/export/render.py)
  4. `hrono-v0-1-0-glossary-dependencies-and-server-cli-internals-18/src-hrono-export-render-py-96.md` (src/hrono/export/render.py)
  5. `hrono-v0-1-0-glossary-dependencies-and-server-cli-internals-18/src-hrono-export-collapse-py-93.md` (src/hrono/export/collapse.py)

### noroot / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs from the hrono-owned directory `paths.cli_workdir` (`context.cli_dir`), an empty directory the client creates if needed. The CLI reads the PROJECT MEMORY of its working directory, so running elsewhere would load the wrong project memory.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `m4-text-completion-seam-3/brief.md`
  3. `m4-text-completion-seam-3/src-hrono-llm-claude-code-py-138.md` (src/hrono/llm/claude_code.py)

### noroot / q18: What does the export collapse do with a requested hop limit below 2?

- expected: clamp, raised to 2, at least 2, treated as 2 in src/hrono/export/collapse.py
- answered: A hop limit (`levels`) below 2 is silently floored to 2, so the export comes out as a 2-level export instead of raising an error.
- cited: src/hrono/server/trees.py
- tools in order: Read > Glob > Read > Read > Read > Read > Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `hrono-s-tree-subsystem-how-trees-are-scoped-to-sources-built-17/brief.md`
  3. `recall-m5-overview-this-group-documents-the-recall-pipeline-13/brief.md`
  4. `hrono-s-tree-subsystem-how-trees-are-scoped-to-sources-built-17/src-hrono-tree-commands-py-293.md` (src/hrono/tree/commands.py)
  5. `hrono-s-tree-subsystem-how-trees-are-scoped-to-sources-built-17/src-hrono-tree-init-py-291.md` (src/hrono/tree/__init__.py)
  6. `summarisation-pipeline-of-the-hrono-codebase-14/brief.md`
  7. `python-sqlite-backend-16/brief.md`
  8. `python-sqlite-backend-16/src-hrono-server-trees-py-246.md` (src/hrono/server/trees.py)
