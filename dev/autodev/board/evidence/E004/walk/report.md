# Export evaluation

Agent: Claude Code `sonnet`, headless, tools Read,Glob. 22 questions x 3 arms.

## Totals

| arm | correct | answer right | source right | reads (mean) | reads to settler (mean) | settler reached | tokens | output tokens | time s (mean) | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| levels-2 | 17/22 | 21/22 | 18/22 | 2.6 | 3.2 | 13/19 | 857498 | 14161 | 10.0 | 1.54 |
| levels-3 | 15/22 | 22/22 | 15/22 | 1.9 | 2.1 | 12/19 | 765125 | 12846 | 9.6 | 1.33 |
| raw | 21/22 | 21/22 | 22/22 | 1.5 | 1.4 | 19/19 | 414901 | 12430 | 9.5 | 0.74 |

## Isolation: verified

Every session ran in a fresh temporary copy of its arm, outside any repository, with `--safe-mode --restricted --strict-mcp-config --no-session-persistence`, only the tools named above, a replaced system prompt, and none of the calling session's CLAUDE_CODE_* variables.

Probe: a CLAUDE.md naming the canary `PELICAN-7731` was planted in the directory above the working directory, and the operator's own ~/.claude/CLAUDE.md carries `graphify`. Both sessions were asked to list every distinctive word their instructions or memory mention.

- control, no isolation flags: quoted `PELICAN-7731`: yes; quoted `graphify`: yes. Reply: "Distinctive items I can see beyond your message: - **Canary word:** PELICAN-7731 (from the project CLAUDE.md, which says to mention it whenever asked) - **Skill:** graphify (`/graphify`, invoked via the Skill tool) - **Package/hook:** sensitive-canary (0.8.1 vendored, 0.8.2 available, `/update-canar"
- isolated, the flags above: quoted `PELICAN-7731`: no; quoted `graphify`: no. Reply: "There are no canary words, skill names, or memory-file codes. The only distinctive names in my instructions are: - **Tools:** Glob, Grep, Read. The prompt also says other tools are deferred, but it doesn't name any. - **Context key:** `userEmail`, which holds the user's email address. - **Environmen"
- isolated session's tools: Glob, Grep, Read; MCP servers: none

Verified means the control quoted `PELICAN-7731` and `graphify` (the probe can see that memory) and the isolated session quoted none of them.

## Per question

### levels-2 (export, `/Users/orest/repos/hrono/.claude/worktrees/E004/.e2e/eval/runs/2026-10-03/levels-2`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 5 | 4 | 1 | 7 | 60145 | 14.8 |
| q02 | shallow | no | yes | no | 1 | - | - | 1 | 11629 | 5.7 |
| q03 | shallow | no | yes | no | 3 | - | - | 3 | 43086 | 10.6 |
| q04 | deep | yes | yes | yes | 2 | - | - | 2 | 25449 | 8.5 |
| q05 | deep | no | yes | no | 1 | - | - | 1 | 11694 | 6.1 |
| q06 | deep | yes | yes | yes | 2 | - | - | 2 | 24943 | 8.6 |
| q07 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 40296 | 10.7 |
| q08 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 47003 | 10.3 |
| q09 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 46782 | 9.9 |
| q10 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 46545 | 13.4 |
| q11 | deep | yes | yes | yes | 4 | 3 | 1 | 4 | 48618 | 10.3 |
| q12 | shallow | no | yes | no | 1 | - | - | 1 | 11712 | 6.7 |
| q13 | deep | yes | yes | yes | 3 | 3 | 1 | 4 | 43042 | 10.3 |
| q14 | deep | yes | yes | yes | 4 | 4 | 1 | 6 | 73807 | 14.3 |
| q15 | deep | no | no | yes | 3 | 3 | 1 | 4 | 42649 | 10.3 |
| q16 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 41259 | 9.5 |
| q17 | deep | yes | yes | yes | 4 | 3 | 1 | 5 | 50938 | 11.3 |
| q18 | deep | yes | yes | yes | 3 | 3 | 1 | 3 | 43409 | 10.0 |
| q19 | shallow | yes | yes | yes | 3 | 3 | 1 | 4 | 59025 | 11.1 |
| q20 | none | yes | yes | yes | 1 | - | - | 2 | 21419 | 8.3 |
| q21 | none | yes | yes | yes | 2 | - | - | 5 | 52286 | 12.3 |
| q22 | none | yes | yes | yes | 1 | - | - | 1 | 11762 | 6.5 |

Pages opened, in order:

- q01: root.md > 15/src-hrono-cli-py-12.md > 15/src-hrono-export-produce-py-90.md > 14/src-hrono-tree-commands-py-260.md > 14/src-hrono-export-init-py-88.md
- q02: root.md
- q03: root.md > 9/brief.md > 9/src-hrono-db-migrations-0002-users-sql-44.md
- q04: root.md > 16/brief.md
- q05: root.md
- q06: root.md > 11/brief.md
- q07: root.md > 11/brief.md > 11/src-hrono-recall-fusion-py-149.md
- q08: root.md > 13/brief.md > 13/src-hrono-cluster-placement-py-25.md
- q09: root.md > 13/brief.md > 13/src-hrono-cluster-repair-py-27.md
- q10: root.md > 12/brief.md > 12/src-hrono-summarize-propagate-py-253.md
- q11: root.md > 10/brief.md > 10/src-hrono-jobs-worker-py-129.md > 10/src-hrono-jobs-worker-py-130.md
- q12: root.md
- q13: root.md > 3/brief.md > 3/src-hrono-ingest-split-constants-py-111.md
- q14: root.md > 4/brief.md > 4/src-hrono-ingest-git-syncer-py-101.md > 5/src-hrono-registry-validation-git-auth-py-170.md
- q15: root.md > 6/brief.md > 6/src-hrono-llm-claude-code-py-132.md
- q16: root.md > 6/brief.md > 6/src-hrono-llm-claude-code-py-132.md
- q17: root.md > 13/brief.md > 13/src-hrono-cluster-incubator-py-18.md > 13/src-hrono-cluster-incubator-py-19.md
- q18: root.md > 16/brief.md > 16/src-hrono-export-collapse-py-89.md
- q19: root.md > 15/src-hrono-paths-py-140.md > 15/src-hrono-profile-store-py-143.md
- q20: root.md
- q21: root.md > 15/readme-md-3.md
- q22: root.md

### levels-3 (export, `/Users/orest/repos/hrono/.claude/worktrees/E004/.e2e/eval/runs/2026-10-03/levels-3`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 4 | 3 | 2 | 7 | 62439 | 13.3 |
| q02 | shallow | no | yes | no | 1 | - | - | 1 | 10217 | 6.0 |
| q03 | shallow | yes | yes | yes | 3 | 2 | 2 | 4 | 40242 | 12.9 |
| q04 | deep | no | yes | no | 1 | - | - | 1 | 10311 | 6.9 |
| q05 | deep | no | yes | no | 1 | - | - | 1 | 10173 | 5.5 |
| q06 | deep | no | yes | no | 1 | - | - | 1 | 10344 | 6.5 |
| q07 | deep | yes | yes | yes | 2 | 2 | 2 | 4 | 54714 | 12.3 |
| q08 | deep | no | yes | no | 1 | - | - | 1 | 10215 | 6.1 |
| q09 | deep | yes | yes | yes | 3 | 2 | 2 | 6 | 57658 | 11.6 |
| q10 | deep | yes | yes | yes | 2 | 2 | 2 | 4 | 57817 | 12.8 |
| q11 | deep | yes | yes | yes | 3 | 2 | 2 | 4 | 42263 | 9.9 |
| q12 | shallow | no | yes | no | 1 | - | - | 1 | 10161 | 5.8 |
| q13 | deep | yes | yes | yes | 2 | 2 | 2 | 5 | 54415 | 11.1 |
| q14 | deep | yes | yes | yes | 2 | 2 | 2 | 4 | 39266 | 9.8 |
| q15 | deep | yes | yes | yes | 3 | 2 | 2 | 4 | 59644 | 12.7 |
| q16 | deep | yes | yes | yes | 2 | 2 | 2 | 3 | 40922 | 9.2 |
| q17 | deep | yes | yes | yes | 3 | 2 | 2 | 5 | 45916 | 11.8 |
| q18 | deep | yes | yes | yes | 2 | 2 | 2 | 5 | 56170 | 10.8 |
| q19 | shallow | no | yes | no | 1 | - | - | 1 | 10193 | 6.2 |
| q20 | none | yes | yes | yes | 1 | - | - | 1 | 10279 | 6.9 |
| q21 | none | yes | yes | yes | 2 | - | - | 4 | 53017 | 13.3 |
| q22 | none | yes | yes | yes | 1 | - | - | 2 | 18749 | 9.5 |

Pages opened, in order:

- q01: root.md > 15/src-hrono-export-produce-py-90.md > 14/src-hrono-tree-commands-py-260.md > 16/src-hrono-export-collapse-py-89.md
- q02: root.md
- q03: root.md > 15/src-hrono-crypto-tokens-py-36.md > 15/src-hrono-auth-users-py-11.md
- q04: root.md
- q05: root.md
- q06: root.md
- q07: root.md > 11/src-hrono-recall-fusion-py-149.md
- q08: root.md
- q09: root.md > 13/src-hrono-cluster-repair-py-27.md > 13/src-hrono-cluster-repair-py-28.md
- q10: root.md > 12/src-hrono-summarize-propagate-py-253.md
- q11: root.md > 10/src-hrono-jobs-worker-py-129.md > 10/src-hrono-jobs-worker-py-130.md
- q12: root.md
- q13: root.md > 3/src-hrono-ingest-split-constants-py-111.md
- q14: root.md > 5/src-hrono-registry-validation-git-auth-py-170.md
- q15: root.md > 6/src-hrono-llm-claude-code-py-132.md > 15/src-hrono-paths-py-140.md
- q16: root.md > 6/src-hrono-llm-claude-code-py-132.md
- q17: root.md > 13/src-hrono-cluster-incubator-py-18.md > 13/src-hrono-cluster-incubator-py-19.md
- q18: root.md > 16/src-hrono-export-collapse-py-89.md
- q19: root.md
- q20: root.md
- q21: root.md > 15/readme-md-3.md
- q22: root.md

### raw (raw, `/Users/orest/repos/hrono/.claude/worktrees/E004/.e2e/eval/runs/2026-10-03/raw`)

| q | kind | correct | answer | source | reads | to settler | depth | tools | tokens | s |
|---|---|---|---|---|---|---|---|---|---|---|
| q01 | shallow | yes | yes | yes | 1 | 1 | 3 | 2 | 12432 | 7.7 |
| q02 | shallow | yes | yes | yes | 1 | 1 | 3 | 3 | 11858 | 7.1 |
| q03 | shallow | yes | yes | yes | 2 | 1 | 3 | 3 | 12118 | 11.3 |
| q04 | deep | yes | yes | yes | 2 | 2 | 3 | 3 | 21913 | 8.4 |
| q05 | deep | yes | yes | yes | 1 | 1 | 3 | 5 | 17929 | 10.0 |
| q06 | deep | yes | yes | yes | 1 | 1 | 3 | 4 | 15818 | 9.1 |
| q07 | deep | yes | yes | yes | 1 | 1 | 3 | 5 | 19694 | 10.8 |
| q08 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 13229 | 7.3 |
| q09 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 15078 | 7.0 |
| q10 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 14069 | 8.9 |
| q11 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 18044 | 9.0 |
| q12 | shallow | yes | yes | yes | 2 | 1 | 4 | 3 | 12945 | 7.1 |
| q13 | deep | yes | yes | yes | 1 | 1 | 4 | 2 | 11249 | 6.7 |
| q14 | deep | yes | yes | yes | 3 | 3 | 4 | 5 | 24951 | 11.7 |
| q15 | deep | no | no | yes | 1 | 1 | 3 | 3 | 10322 | 8.6 |
| q16 | deep | yes | yes | yes | 1 | 1 | 3 | 3 | 10153 | 7.4 |
| q17 | deep | yes | yes | yes | 1 | 1 | 3 | 2 | 14671 | 8.9 |
| q18 | deep | yes | yes | yes | 2 | 2 | 3 | 3 | 21979 | 9.1 |
| q19 | shallow | yes | yes | yes | 4 | 4 | 3 | 11 | 59854 | 17.5 |
| q20 | none | yes | yes | yes | 2 | - | - | 5 | 17160 | 9.0 |
| q21 | none | yes | yes | yes | 1 | - | - | 7 | 22277 | 11.6 |
| q22 | none | yes | yes | yes | 3 | - | - | 9 | 37158 | 14.9 |

Pages opened, in order:

- q01: tree/commands.py
- q02: summarize/pool.py
- q03: crypto/tokens.py > auth/users.py
- q04: ui/export.py > export/collapse.py
- q05: recall/fusion.py
- q06: recall/fusion.py
- q07: recall/fusion.py
- q08: cluster/placement.py
- q09: cluster/repair.py
- q10: summarize/propagate.py
- q11: jobs/worker.py
- q12: split/constants.py > GLOSSARY.md
- q13: split/constants.py
- q14: ingest/git_syncer.py > ingest/git_reader.py > validation/git_auth.py
- q15: llm/claude_code.py
- q16: llm/claude_code.py
- q17: cluster/incubator.py
- q18: ui/export.py > export/collapse.py
- q19: hrono/paths.py > README.md > hrono/cli.py > profile/store.py
- q20: README.md > pyproject.toml
- q21: README.md
- q22: GLOSSARY.md > server/graph.py > README.md

## Failed paths

### levels-2 / q02: Which environment variable sets how many LLM calls one op runs at once, and what is the default?

- expected: HRONO_LLM_CONCURRENCY in src/hrono/summarize/pool.py, README.md
- answered: `HRONO_LLM_CONCURRENCY` sets how many LLM calls an op runs at once. It defaults to 4.
- cited: root.md
- tools in order: Read
- pages opened in order:
  1. `root.md`

### levels-2 / q03: How does hrono store a user's API token in the database?

- expected: sha-256, sha256 in src/hrono/crypto/tokens.py, src/hrono/auth/users.py
- answered: Only a SHA-256 hash of the token is stored, in the `users.token_hash` column (TEXT NOT NULL UNIQUE). The plaintext token is shown once and not kept.
- cited: src/hrono/db/migrations/0002_users.sql
- tools in order: Read > Read > Read
- pages opened in order:
  1. `root.md`
  2. `these-condensations-describe-the-sqlite-schema-of-hrono-a-sy-9/brief.md`
  3. `these-condensations-describe-the-sqlite-schema-of-hrono-a-sy-9/src-hrono-db-migrations-0002-users-sql-44.md` (src/hrono/db/migrations/0002_users.sql)

### levels-2 / q05: What is the k constant of the reciprocal rank fusion that recall uses?

- expected: 60 in src/hrono/recall/fusion.py
- answered: K = 60 (weighted RRF, with weights 0.7 vector and 0.3 keyword).
- cited: root.md
- tools in order: Read
- pages opened in order:
  1. `root.md`

### levels-2 / q12: What is the target size in bytes of a passage, the unit recall injects?

- expected: 800 in src/hrono/ingest/split/constants.py, GLOSSARY.md, CONTRIBUTING.md
- answered: A passage targets about 800 bytes (~800 B).
- cited: root.md
- tools in order: Read
- pages opened in order:
  1. `root.md`

### levels-2 / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: It runs from `paths.cli_workdir`, a directory hrono owns, because the CLI reads the project memory of its working directory. An empty directory keeps the operator's CLAUDE.md and other project memory out of the call.
- cited: src/hrono/llm/claude_code.py
- tools in order: Read > Read > Glob > Read
- pages opened in order:
  1. `root.md`
  2. `these-condensations-document-the-llm-access-layer-of-the-hro-6/brief.md`
  3. `these-condensations-document-the-llm-access-layer-of-the-hro-6/src-hrono-llm-claude-code-py-132.md` (src/hrono/llm/claude_code.py)

### levels-3 / q02: Which environment variable sets how many LLM calls one op runs at once, and what is the default?

- expected: HRONO_LLM_CONCURRENCY in src/hrono/summarize/pool.py, README.md
- answered: `HRONO_LLM_CONCURRENCY` sets it, and the default is 4.
- cited: root.md
- tools in order: Read
- pages opened in order:
  1. `root.md`

### levels-3 / q04: In the export, how many entries is one index page budgeted to list?

- expected: 40 in src/hrono/export/collapse.py
- answered: One index page is budgeted for 40 entries (WIDTH=40 per page).
- cited: root.md
- tools in order: Read
- pages opened in order:
  1. `root.md`

### levels-3 / q05: What is the k constant of the reciprocal rank fusion that recall uses?

- expected: 60 in src/hrono/recall/fusion.py
- answered: Recall uses weighted reciprocal rank fusion with K=60. The weights are 0.7 for the vector leg and 0.3 for the keyword leg, and results are capped at 10.
- cited: root.md
- tools in order: Read
- pages opened in order:
  1. `root.md`

### levels-3 / q06: How does recall weight its vector leg against its keyword leg when fusing them?

- expected: 0.7 in src/hrono/recall/fusion.py
- answered: Recall fuses the legs with weighted RRF (K=60), giving the vector leg 0.7 and the keyword (FTS5 BM25) leg 0.3. Results are capped at 10, with a 40% per-document reserve.
- cited: root.md
- tools in order: Read
- pages opened in order:
  1. `root.md`

### levels-3 / q08: What similarity threshold (TAU) decides whether a new section is placed into an existing cluster?

- expected: 0.7 in src/hrono/cluster/placement.py
- answered: TAU is 0.70. In `place`/`assign_or_park`, a new section goes into an existing cluster (topic) only if its similarity reaches this threshold. Sections that don't fit go to the pending pool (the incubator).
- cited: root.md
- tools in order: Read
- pages opened in order:
  1. `root.md`

### levels-3 / q12: What is the target size in bytes of a passage, the unit recall injects?

- expected: 800 in src/hrono/ingest/split/constants.py, GLOSSARY.md, CONTRIBUTING.md
- answered: A passage, the retrieval unit that recall injects, targets about 800 bytes. That figure is approximate ("~800 B"), not an exact constant.
- cited: root.md
- tools in order: Read
- pages opened in order:
  1. `root.md`

### levels-3 / q19: Which environment variable moves the CLI's profile config file to another directory?

- expected: HRONO_HOME in src/hrono/profile/store.py
- answered: `HRONO_HOME` moves the directory that holds the CLI's profile `config.toml`. If it isn't set, the default is `~/.hrono`.
- cited: root.md
- tools in order: Read
- pages opened in order:
  1. `root.md`

### raw / q15: In which directory does the claude-code provider run the Claude Code CLI, and why there?

- expected: cache/cli in src/hrono/paths.py, src/hrono/llm/claude_code.py
- answered: The CLI runs in hrono's own `paths.cli_workdir`, an empty directory the client creates, because the CLI reads the project memory of its working directory. Running there keeps the user's project memory out of the call, and `--safe-mode` already covers the same thing.
- cited: src/hrono/llm/claude_code.py
- tools in order: Glob > Glob > Read
- pages opened in order:
  1. `src/hrono/llm/claude_code.py` (src/hrono/llm/claude_code.py)
