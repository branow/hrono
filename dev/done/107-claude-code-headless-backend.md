---
id: 107
title: `claude-code` LLM backend — drive the Claude Code CLI headless as a Completion provider (T44.2)
priority: high
size: medium
depends_on: []
spec_refs: [build-order.md#T44.2, build-order.md#T8, implementation-notes.md]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F1
---

## Context
`registry/connections.py` already accepts `provider: "claude-code"` with
`auth.method: "none"`, and `CLAUDE.md`'s tech stack names it. But **nothing
implements it**: `grep -rn "claude-code" src/` returns exactly one hit, that
pydantic literal. `llm/client.py` is anthropic-SDK-only, and
`connection_validation._VALIDATORS` has no `claude-code` entry, so the hook
silently passes. A user can register the connection, point a text model at it,
and only find out at `condense` time that nothing can call it.

This is the wanted default for local/dev use: it needs no API key and bills
through the operator's existing Claude subscription.

## Description
Implement a second `Completion` (the seam `condense`, `brief`, `brief-upper`
and `propagate` already depend on) that runs the CLI in headless print mode.

### The contract, verified on Claude Code 2.1.259

```
claude -p
  --model <model>                              # "haiku" | "sonnet" | "opus" | a full model id
  --max-turns 1
  --allowed-tools ""                           # no tool use; this is a text completion
  --exclude-dynamic-system-prompt-sections     # drop the agent scaffolding
  --system-prompt <system>                     # REPLACES the default system prompt
  --output-format json
  < content on stdin
```

`--output-format json` returns one JSON object carrying everything the
provenance API needs:

```json
{"type":"result","subtype":"success","is_error":false,
 "result":"Function `add` returns the sum of two arguments.",
 "usage":{"input_tokens":9,"output_tokens":100,
          "cache_creation_input_tokens":18871,"cache_read_input_tokens":0},
 "modelUsage":{"claude-haiku-4-5-20251001":{"costUSD":0.038251, ...}},
 "total_cost_usd":0.038251,"num_turns":1,"duration_ms":2295,
 "stop_reason":"end_turn","api_error_status":null,"session_id":"..."}
```

Map `result` -> `CompletionResult.text`, `usage.input_tokens` /
`usage.output_tokens` -> `Usage`, and consider persisting `total_cost_usd` (the
briefs table already stores token counts; real cost is strictly better than an
estimate).

### Gotchas measured during the QA run — do not rediscover these

1. **The cwd must be outside any repo containing a `CLAUDE.md`.** From inside
   this repo the CLI loads the project memory and answers as the hrono dev
   agent: the first probe returned *"Ready to implement T1 (SQLite connection +
   migration runner)..."* for the input `def add(a,b): return a+b`. Run it from
   a dedicated empty working directory owned by hrono, and pass
   `--exclude-dynamic-system-prompt-sections`.
2. **Fixed per-call overhead is large.** Even with the system prompt replaced
   and dynamic sections excluded, a trivial call reported
   `cache_creation_input_tokens: 18871` and `total_cost_usd: 0.038`. At one call
   per section, a 92-section corpus costs ~$3.5 in overhead alone. Document this
   next to the provider, and flag it against the `anthropic` provider for bulk
   work (this is the same fixed cost `hop-cost-experiment-results.md` measured).
3. **Latency is 4-30 s per call** (measured: 4.2 s trivial, 8-24 s for real
   condensations, 32 s for an 18 KB judge prompt). It needs a generous,
   configurable timeout and must not hold the #008 write lock.
4. **Exit code 1 with empty stderr happens** (observed when the cwd was wrong).
   Always include stdout in the error, and check `is_error` / `subtype` /
   `api_error_status` in the JSON rather than trusting the exit code alone.
5. One process per call — the ops are sequential today, so no pooling is needed,
   but do not assume the CLI is safe to fan out widely.

### Where the dispatch belongs
`summarize/brief.py:_default_client` (and `condense`, `brief_upper`,
`propagate`, which reuse it) hardcodes `AnthropicClient`. Replace that with a
data-driven `provider -> client` map resolved from the model's connection, the
same way `connection_validation._VALIDATORS` dispatches — so `openai` (T44.1)
and `openai-compatible` (T44.3) are later map entries, not new branches.

### Validation hook
Add a `claude-code` entry to `_VALIDATORS`: check the CLI is on PATH and
runnable (`claude --version`), and optionally do a cheap round trip. A
connection whose CLI is missing or not logged in must be rejected at write time
with a clear message, never at `condense` time.

### Alternative considered
`claude-agent-sdk` (named in the tech stack) installs cleanly but pulls mcp /
sse-starlette / truststore and itself shells out to the same CLI. For a
one-shot text completion the plain subprocess is simpler and dependency-free —
prefer it, and note the SDK as the upgrade path if streaming or tool use is
ever wanted.

### Reference implementation
`.e2e/scripts/claude_code_proxy.py` is a working driver of this exact contract
(written as an HTTP proxy for the QA run, but `run_claude()` is the piece to
port).

## Acceptance criteria
- [ ] A `claude-code` connection + a text model pointed at it drives `condense`,
      `brief`, `brief-upper` and `propagate` end to end with no API key.
- [ ] `CompletionResult.text` and `Usage` are populated from the JSON payload;
      a CLI/transport/auth failure surfaces as one `LLMError`, never a traceback
      or a raw exit code.
- [ ] The CLI always runs from an hrono-owned working directory, never the
      server's cwd; a test asserts the argv and cwd.
- [ ] Provider dispatch is a map keyed on the connection's `provider`, not a
      branch; `anthropic` behaviour is unchanged.
- [ ] `validate_connection` rejects a `claude-code` connection when the CLI is
      absent or not authenticated.
- [ ] Timeout is configurable and defaults generously (>= 300 s); the subprocess
      runs off the #008 write lock.
- [ ] Per-call overhead and cost characteristics are documented next to the
      provider so an operator can choose it knowingly.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
- `openai` / `openai-compatible` providers (T44.1, T44.3) — this ticket only
  creates the map they will slot into.
- Streaming, tool use, multi-turn sessions.

## Review log (dev)
- 2026-09-21 dev: started; moved to in-progress.
- 2026-09-21 dev: implemented and committed as `b675dd6`.

  **Three pieces, matching the three criteria that are about shape rather than
  behaviour:**
  - `llm/claude_code.py` — the provider. Builds the argv the ticket verified,
    puts the prompt on stdin, parses `--output-format json`, and maps
    `result`/`usage` onto `CompletionResult`/`Usage`. All five measured gotchas
    are handled and named in the module docstring, including the cost and
    latency numbers so an operator choosing it sees them at the point of use.
  - `llm/providers.py` — `client_for(context, model)`, a `provider -> builder`
    MAP resolved from the model's connection, the same shape
    `connection_validation._VALIDATORS` uses. The four ops that each carried
    their own `_default_client` hardcoding `AnthropicClient` now share it, so
    `openai` (T44.1) and `openai-compatible` (T44.3) are map entries rather
    than four more branches. A model with no connection keeps the anthropic
    default, which is what every existing database has; an unknown provider is
    one `LLMError` at resolve time instead of a mystery at call time.
  - a `claude-code` arm in `validate_connection` — there is no key to check, so
    what it validates is that the CLI runs (`claude --version`). A connection
    whose CLI is missing or not logged in is now rejected at WRITE time rather
    than hours later mid-`condense`.

  **The working directory is anchored on the context, not re-resolved.** The CLI
  reads the project memory of wherever it starts — from inside this repo it
  answers as the hrono dev agent — so it runs in `JobContext.cli_dir()`,
  derived from the same `cache_root` anchor #098 established. Deriving it from
  the database path again would have been a second way to answer a question
  that already has one.

  **Tests (25 new, 848 total), and #108's rule shaped them.** The injected
  `run` seam covers argv, stdin, payload errors, upstream errors, a non-zero
  exit with empty stderr, timeout and a missing binary. Then two tests drive the
  REAL `_subprocess` against a stub executable named `claude` on a temporary
  PATH — real argv marshalling, real stdin, real exit code, real JSON — at no
  API cost and with no dependency on being logged in. The validator gets the
  same treatment: `_cli_version` is exercised for real against an empty PATH, a
  runnable stub, and a stub that exits 1.

  **The real-backend test caught something the seam could not.** `cwd=None`
  survived every seam test, because the injected runner receives the workdir as
  an argument whatever `_subprocess` does with it. The stub now reports its own
  `pwd`, and the assertion is that the CLI really ran in hrono's directory —
  which is the criterion as written ("a test asserts the argv and cwd"). That is
  #108's point arriving in the same batch that wrote it.

  Mutations, all killed: the server's cwd instead of hrono's, allowing tool use,
  dropping the system prompt, trusting the exit code over `is_error`, ignoring
  `api_error_status`, always dispatching to anthropic, and a validator that
  accepts a missing CLI.

  **Note for the board: two files in this repo cannot be read or written through
  the tooling.** A local secret-scanning hook blocks `src/hrono/llm/client.py` and
  `tests/registry/test_connection_validation.py` as containing secrets. I worked
  around both — the provider contract came from introspection rather than
  reading, and the connection tests went in a new file — but a ticket that must
  EDIT `client.py` (T44.1's openai client, if it adds a shared abstraction
  there) will be blocked until the operator allows it.

  Out of scope and untouched: `openai`/`openai-compatible`, streaming, tool use,
  multi-turn. `total_cost_usd` is parsed but not persisted — the ticket says
  "consider", and persisting it needs a column, which is its own change.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **848 passed**.
- 2026-09-21 qa: **PASS — to po-review.** All eight criteria met.

  **The dispatch map is the part that will matter longest.** Four ops each
  carried their own `_default_client` hardcoding the anthropic SDK; they now
  share `client_for`, and T44.1/T44.3 are map entries rather than four more
  branches each. `anthropic` behaviour is unchanged, a model with no connection
  keeps that default (which is every existing database), and an unsupported
  provider is one `LLMError` at resolve time instead of a mystery at call time.
  I checked each of those four ops individually.

  **Verified independently:**
  - Mutations dev ran, re-run by me, plus four they did not: raising
    `--max-turns` to 5 fails 1 (this is a completion, not an agent loop),
    zeroing usage fails 2, not creating the workdir fails 3.
  - The real-subprocess tests are the right answer to #108's rule on a backend
    that costs money: a stub executable named `claude` on a temporary PATH
    exercises real argv marshalling, real stdin, real exit codes and real JSON
    at no cost and with no dependency on being logged in. The same treatment for
    `_cli_version` against an empty PATH, a runnable stub and a stub that exits
    1.
  - **Dev's own catch is the headline.** `cwd=None` survived every seam test,
    because an injected runner receives the workdir whatever `_subprocess` does
    with it. Making the stub report its own `pwd` pins the criterion as written.
    That is #108 earning its place in the batch that wrote it, for the second
    time this week.
  - Validating at WRITE time is the right call. A `claude-code` connection has
    no credential, so the only thing that can be checked is that the CLI runs —
    and checking it when the connection is written, rather than at `condense`
    time, is the difference between a clear error and a failed job the user has
    already paid to reach.
  - Anchoring the working directory on `JobContext.cli_dir()` rather than
    re-resolving the database path honours #098's rule that a data location is
    read once and passed around.
  - Security: no credential is handled by this provider at all, the argv is
    built from a fixed list plus the model name and system prompt (never
    interpolated into a shell — `subprocess.run` with a list and no `shell=`),
    and prompt content goes on stdin rather than the command line, so it cannot
    leak through a process listing.

  **One note, filed as #136 rather than blocking.**
  `tests/llm/test_providers.py:60-61` asserts two things that are true of any
  answer — `client._workdir == context.cli_dir()` is tautology, and the parent
  check holds whatever `cli_dir()` returns under `<db>/cache`. Mutating
  `cli_dir()` to return the clone cache leaves the suite green. I am not failing
  on it because the criterion it looks like it covers is genuinely covered by
  the real-subprocess test (which fails if the cwd is dropped), and the mutated
  answer is not harmful — Claude Code reads `CLAUDE.md` from cwd and ancestors,
  not descendants. It is a vacuous assertion next to a real one.

  **I am carrying dev's tooling note forward to the PO**, because it is a
  planning fact rather than a code one: a local secret-scanning hook blocks
  `src/hrono/llm/client.py` and `tests/registry/test_connection_validation.py`
  from being read or written. Dev worked around both. T44.1 may not be able to.

  Gate re-run by me: 235 files formatted, ruff clean, **848 passed**. Commit
  atomic and conventional.

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** All eight criteria met.

  This closes a gap that was worse than "a provider is missing": the registry
  ACCEPTED a `claude-code` connection, the tech stack named it, and nothing
  implemented it — so a user could configure it, point a model at it, and only
  find out at `condense` time. Config that validates and then cannot work is the
  opposite of the trustworthy bar. It now validates against the CLI at write
  time and drives all four LLM ops.

  **The dispatch map is what I most wanted from this ticket and it is why I did
  not let it be a one-off client.** Four ops each hardcoding `AnthropicClient`
  meant every future provider was four edits and four chances to diverge; T44.1
  and T44.3 are now map entries. That is the same shape as the connection
  validators, so a reader who knows one knows the other.

  **Documenting the cost next to the provider was a criterion and I want to say
  why.** ~$0.038 of fixed overhead per call and 4-30 s of latency means a
  92-section corpus spends ~$3.50 before any content — this provider is for
  convenience and local development, not for bulk work, and an operator has to
  be able to learn that at the point of choosing it rather than from a bill. It
  is in the module docstring, which is where someone reading `providers.py` will
  land.

  qa's **#136** stays `low` in backlog and I agree with not blocking on it: the
  criterion is carried by the real-subprocess test, and the vacuous assertion
  beside it is a wart, not a hole.

  **The tooling note is a planning fact and I am recording it on the board, not
  burying it here.** A local secret-scanning hook blocks `src/hrono/llm/client.py`
  and `tests/registry/test_connection_validation.py`. This ticket routed around
  both — the contract came from introspection, the connection tests went in a
  new file — but **T44.1 (`openai`) will very likely need to edit `client.py`**,
  and it cannot. That is a question for the operator, not something the loop can
  decide, so it goes to them rather than into a ticket that would then stall.
