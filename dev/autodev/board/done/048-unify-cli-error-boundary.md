---
id: 048
title: unify CLI error rendering into one boundary, replacing scattered per-command mapping
priority: medium
size: medium
depends_on: [009, 011, 027, 033]
spec_refs: [implementation-notes.md#cli]
---

## Context
Mapping a domain exception to a CLI "(message, exit code)" is currently scattered
across the CLI: `_guard` in `context/commands.py` (MalformedConfig), inline
`try/except DuplicateContext / UnknownContext` in each context command,
`_key_error_message` in `cli.py` (MasterKeyError), and the admin-command
messages. Each command re-implements presentation. The store correctly raises
typed domain errors (that part is right); what is missing is a single CLI
presentation boundary that renders them uniformly, so command bodies hold only
happy-path logic. Precedent exists server-side (the #027 `AppError` envelope +
the client `cli_message()`), but the CLI command layer never got the same
treatment. `_guard` is a symptom of that missing boundary.

## Description
Introduce one CLI error boundary and route all command error rendering through
it:
- A single mapping from domain exception type -> (message, exit code) as DATA
  (a dict/table), not per-command `try/except` ladders — e.g. MalformedConfig,
  DuplicateContext, UnknownContext, MasterKeyError, and the client
  Unauthorized/Forbidden/NoProfile already handled in `client/http.py`.
- Apply it once (a Typer error handler, or a thin wrapper that every command is
  routed through) so commands raise typed errors and never format messages
  themselves.
- Remove `_guard`, `_key_error_message`, and the inline per-command try/excepts
  in favor of the one boundary.
- Preserve current behavior exactly: same messages, same non-zero exit codes,
  token never printed.

## Acceptance criteria
- [ ] One data-driven mapping renders every CLI domain error; no per-command
      error-formatting remains (`_guard` and `_key_error_message` gone).
- [ ] All existing CLI error messages and exit codes are unchanged (covered by
      the existing tests, extended where needed).
- [ ] Adding a new command requires no new error-handling boilerplate.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean.

## Out of scope
- The server-side `AppError` envelope (already done, #027) — this is the CLI
  client presentation layer only.
- Changing which exceptions the stores raise (the domain errors are correct).

## Review log
- 2026-08-22 stakeholder + PO: raised during review of #011 (`_guard`). Agreed
  the malformed-config mapping is presentation and does not belong per-command;
  scattered CLI error mapping should collapse into one boundary.

## Review log (dev)
- 2026-09-22 dev: implemented and committed as `d8b0d36`. All four criteria.

  **Applied ONCE, as the Typer group's `invoke`** — which is what makes "adding
  a command requires no new error-handling boilerplate" true rather than
  aspirational. A command body now carries none at all: it calls the client and
  returns, and everything below the root group, nested groups included, passes
  through one boundary. The alternative shapes (a shared `run(action)` helper, a
  decorator) would each have left one line of boilerplate per command, which is
  how the six copies started.

  **`RENDERERS` is a table, not a ladder**: exception type -> the function that
  renders it, ordered most-specific first. A new domain error is an entry.

  Removed: `_run` from `tree`, `jobs`, `registry`, `profile` and `admin`
  commands (five near-identical copies), the inline `except ClientError` in
  `recall`, and the `except AppError` in `admin reset-token` and `serve`. Net
  **-214 / +224 lines** including the new boundary and its tests, and every
  command body lost its `def action()` closure — the indirection existed only to
  hand a callable to `_run`.

  **`reset` keeps its handler and re-raises**, which is the one place the
  distinction matters: a wipe that stopped part-way owes the operator the list
  of what it destroyed, and that report is behaviour, not presentation. It does
  the report and lets the boundary render the message.

  **I made this ticket worse before fixing it.** #138 added two more `_run`
  copies this session — I wrote them by copying `tree/commands.py` without
  noticing this card existed. That is exactly the decay the ticket predicted in
  August, observed in the act.

  Behaviour is unchanged: the same messages, the same exit code 1, and the token
  still never printed. Tests (3 new, 931 total): the boundary renders a client
  error as one line with no traceback; and a structural test asserting no
  command module contains `except ClientError` or `def _run(` — the criterion
  that stops this regrowing, since a convention nobody can check erodes.
  Mutations: not installing the boundary fails 22, swallowing the message fails
  22, exit code 0 fails 26, and swallowing an UNKNOWN error instead of
  re-raising fails 2 (a boundary that eats what it cannot render would hide
  real bugs).

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **931 passed**.
- 2026-09-22 qa: **PASS — to po-review.** All four criteria met.

  **Installing the boundary as the Typer group's `invoke` is the right shape**
  and it is the only one that makes criterion 3 literally true. A shared
  `run(action)` or a decorator still leaves one line to copy, and one line to
  copy is how six copies happened.

  **Verified:**
  - No `_run` and no `except ClientError` survives in any command module — and
    there is a STRUCTURAL test asserting that, which is what stops it
    regrowing. I checked the whole tree by grep as well: the only remaining
    `except AppError` is `reset`'s, which re-raises after reporting what it
    destroyed. That one is behaviour, not presentation, and keeping it is right.
  - Mutations dev ran, re-run by me: not installing the boundary fails 22,
    swallowing the message fails 22, exit code 0 fails 26, swallowing an unknown
    error fails 2.
  - **One of mine survived and produced the better fix.** Reversing the renderer
    order changed nothing, because no two entries are related — the docstring
    claimed "ordered most-specific first, so a subclass can render differently
    from its base", describing a mechanism the table does not exercise. That is
    the #123 shape in miniature: documentation asserting a behaviour the code
    does not demonstrate. It now says the order decides only when an entry
    subclasses another, that none do today, and that it is a rule for the next
    person. And it is PINNED by a test over a synthetic pair, so the rule fails
    loudly when someone adds the entry that matters.
  - The unmapped case is pinned too: an error the table does not know escapes as
    itself. A boundary that renders everything would turn a genuine bug into a
    tidy one-line message, which is the worst thing a boundary can do.

  Dev's note that #138 added two of the six copies this session is worth
  keeping. The decay this ticket predicted in August happened in front of us.

  Gate re-run by me: **933 passed**, ruff clean.

## Review log (PO)
- 2026-09-22 PO: **PASSES — closed to done.** All four criteria met.

  Raised in August off a single `_guard`; by the time it was picked up there
  were eight handlers, two of them added this week while building the config
  CLI. **That is the argument for the ticket, delivered by the delay in doing
  it** — a pattern nobody owns gets copied by whoever needs it next, including
  by people who have read the card.

  The structural test is what makes this stick. "No command module contains
  `except ClientError`" is a rule a reviewer can check in a second, and it fails
  the moment someone copies the old shape. Conventions decay at exactly the
  moment somebody is being helpful; a failing test is the only form of
  "please don't" that survives.

  **qa's surviving mutation is the one I most want noted.** The docstring
  claimed the table was ordered most-specific first so a subclass could render
  differently — true of the mechanism, false of the contents, since no two
  entries are related. Documentation asserting a behaviour the code does not
  demonstrate is the same defect as #123's phantom corrective and #140's
  two-leg fusion, and this is the third time this week. The fix is right: say
  what is true now, state the rule for later, and pin the rule with a test so
  it is not a promise.

  Behaviour unchanged, messages unchanged, token still never printed, and every
  command body is now happy-path only.
