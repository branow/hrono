# Findings: BC Registries evaluation

Numbered in the order they were found. Status is **fixed** (with the commit),
**open**, or **note** (an observation, not a defect). The step-by-step log in
`README.md` shows where each one came up.

## Build robustness and cost

- **E1, fixed `9e8318b`. One call per section.** Every condense call paid the
  claude-code harness, about 19k cached tokens and several seconds.
  Condense now packs up to 8 sections or 32 KB into one call. On this corpus
  that was 1,240 calls for 8,281 condensations, about 6.7 sections per call.
- **E7, note. Throughput.** At width 4, a pack averaged ~5.2 sections in
  31.8 s, with ~2,550 output tokens. At width 8, condense ran at about 94
  sections per minute. Width is `HRONO_LLM_CONCURRENCY`.
- **E8, open. Shutdown orphans.** SIGTERM to `hrono serve` leaves in-flight
  `claude -p` subprocesses running. Their work is paid for and then thrown
  away.
- **E9, fixed `4d5e8b2`. One pack stopped the build.** A pack holding a
  vendored base64 font and a large OpenAPI YAML hit `error_max_turns`, and
  that one error stopped condense 1,484 sections in. A failed pack is now
  answered one section at a time, and a section that is still unfinished
  alone is refused (`unfinished`) instead of retried on every run.
- **E10, fixed `8f8d3aa`. Encoded blobs.** 758 of 9,827 sections, 17% of
  the bytes, were encoded data: base64 inlined in HTML report and email
  templates, `vfs_fonts.js`, minified `faker.js` and `cheerio.js`, and
  gold-file JSON with base64 PDFs. They caused E9 and a 300 s timeout. The
  split now drops any section where whitespace-free runs of 400+ bytes cover
  more than half of it.
- **E12, fixed `5e5f211`. A 429 stopped the build.** The SDK clients retry
  it; the claude-code client didn't. It now retries 429/503/529 at 10, 30
  and 90 s.
- **E14, open. A timeout still stops the build.** A single call over the
  300 s limit fails the op. After E10 it should be rare; watch for it.
- **E15, fixed `a362385`. A usage limit stopped the build.** The
  subscription's usage limit answers 429 for hours. The build died at brief
  367 of 489 after the 130 s backoff was spent. The client now keeps
  retrying every 5 minutes for up to 6 hours, and stops if its job is
  stopped.
- **E16, fixed `a7f5771`. Vendored bower trees.** The SchemaSpy docs in
  sbc-auth and sbc-pay vendor `bower/` copies of jquery, jquery-ui,
  codemirror and bootstrap: 626 sections, and the root brief described
  "third-party front-end stacks". These paths are now ignored by default.
- **E11, open. The API path's output cap.** `AnthropicClient` defaults to
  `max_tokens` 4096 and does not check `stop_reason`. A full 8-section pack
  is close to that, and a truncated reply silently loses its last results.
  The fallback re-asks those sections alone, so nothing is lost, but calls
  are wasted. Not exercised in this eval, which used claude-code.

## Tree quality

- **E17, open. The top split means nothing.** The root has 2 children, and
  both briefs describe "the BC Registries ecosystem". Briefs also comment on
  their input ("nearly all fragments are truncated, duplicated, generated or
  test data").
- **E18, open. Identifiers not in the source.** 84 of 517 briefs carry an
  identifier that is not in their members (`unfaithful`). For example,
  `addressIds` appears where the code has `address_ids`. The prompt says to
  copy identifiers verbatim.
- **E19, open. Meta titles.** Many briefs open with "This is a set of
  condensed notes on…" or "What this is: …". Titles and node URIs are taken
  from that opening, e.g.
  `node://hrono/nodes/432/this-is-a-set-of-condensed-notes-on-the-pytest-suites-for-an`.
- **E20, open. The cold build ignores the repair cap.** The cold build left
  66 of 489 leaves over `MAX_CAP` 30 (max 89). The first incremental sync
  after it ran 120 splits, 135 brief and 31 brief-upper calls, $11.39 of
  its cost, repairing the build rather than applying the change. Build and
  repair should agree on the cap, so a sync costs what its diff costs.
- **E21, note. Cross-repo leaves.** 202 of 489 leaves (178 of 536 after the
  sync) hold sections from more than one repository. Whether that is a
  real cross-cutting concern or a mixed-up topic needs a look per leaf.
- **E22, note. Recall.** Of five questions, recall found the core code for
  most of them (`authorization.py`, `role_validator.py`,
  `update_colin_filings.py`, `fee_schedule.py`, `payment_service.py`). It
  also ranked an email template, a CI workflow and UI dialogs first for
  "how is a filing payment processed" and "how does the COLIN sync work".
  See `data/01-cold-build-and-sync0/recall_samples.md`.
- **E23, open. Core code is clustered with build, test and fixture files.**
  This was found by tracing the question "once a filing is paid, how is it
  applied to the business, and what differs for future-effective filings?"
  (`../2026-10-bc-registries-agents/`, question `lear-filings-1`) through
  the tree. The five files that answer it land in these leaves:
  - `entity_pay/worker.py` (the payment listener) is in "condensed
    descriptions of python test suites helpers".
  - `entity_filer/worker.py` (it applies the filing) is in that same
    test-suites leaf, and also in "filing queue worker".
  - `jobs/future-effective-filings/file_future_effective.py` is in
    "container and shell entrypoints", "Dockerfile summaries" and "17
    Makefiles".
  - `legal_api/models/filing.py` is in "corpus fixtures", among others.
  - Only `business_pay/resources/pay_filer.py` sits in a fitting leaf,
    "Business-Pay service".

  An agent looking for payments or filings never opens those leaves.
- **E24, open. No brief tells a flow that crosses leaves.** The facts of
  the flow in E23 (pay listener → filer queue → entity-filer applies it;
  future-effective filings wait for a scheduled job) are each present in
  some leaf. They are spread over five unrelated leaves in different
  branches, though, so no upper brief can state the flow. Agents answering
  architecture questions get routing at best, and no explanation.
- **E25, open. Leaf briefs are file catalogs.** The best-placed leaf above,
  "Business-Pay service" (1,000 words), is about half licence text,
  gunicorn and WSGI settings, Sentry and environment defaults. The
  behaviour the question needs (mark PAID, route to staff review or the
  filer queue, notify the emailer) is the other half. Briefs walk through
  files one by one instead of saying what the component does, what it
  consumes and emits, and who calls it.
- **E26, open. One service is scattered across the whole tree.** This was
  found by a second trace, question `pay-3`: "how is an account lock after
  a bounced debit or an overdue statement modeled, enforced and lifted?",
  on the export with `--levels 3`.
  - The 8 pay-api, pay-queue and payment-job files that answer it sit in
    about 12 leaves under 5 different top groups. One of those groups is
    the "lear ecosystem" group, and another is "notebooks, migrations,
    models and tests".
  - One file can land in up to 3 leaves in different groups. For example,
    `services/payment_account.py` has its sections split across "payapi
    source files", "pay-api flask service" and "python billing payment
    codebase".
  - An agent that picks the "payments" branch sees a fraction of the
    payment service.
- **E27, open. Top-level groups and leaf titles do not route.** Of root's
  25 groups (with `--levels 3`), 3 are SchemaSpy documentation, 2 are
  Postman, and one is "API spec fragments and AJV internals". Product code
  shares 4–5 vague groups with tests and fixtures. Some leaf titles come
  from boilerplate, for example
  `apache-2-0-licensed-source-files-2024-province-of-british-co`, which
  holds `pad_service.py` and `base_payment_system.py`.
- **E28, open. Briefs name things without saying what they do.** Every
  identifier of the `pay-3` answer appears somewhere: `has_nsf_invoices`,
  `ensure_no_payment_blockers`, `unlock_frozen_accounts`, `PAD_STOP`,
  `FREEZE`. But they appear as one-line fragments in 6 or more leaves, and
  often as bare lists ("`unlock_frozen_accounts`, `delete_account`,
  `enable_eft` and the fee methods"). The concept "an account lock: set on
  NSF or overdue, blocks new invoices, lifted by a card payment" is stated
  nowhere. The same identifiers also recur in test and migration leaves,
  which adds noise.
- **E29, note. Secrets copied from the source into briefs.** A test-support
  brief carries an `.env`-style test password copied from the repository.
  It is a test value, but the export trips secret scanners (the
  sensitive-canary hook blocked reading it). Condense and brief should not
  copy credential-looking values.

## Operator experience

- **E2, open. README `-f -`.** `hrono <collection> set NAME -f -` is rejected
  ("File '-' does not exist"). Stdin is read when `-f` is omitted. Every
  `set` example in the README uses `-f -`.
- **E3, open. README git auth.** The README's git source example
  `"auth": {}` is rejected (`git.auth.method: Field required`). It needs
  `{"method": "none"}`.
- **E4, open. Token with a newline.** `profile add` and `set-token` accept
  a token containing a newline, and every later command fails.
- **E5, open. "Cannot reach server".** That failure is reported as "Cannot
  reach hrono server … Is 'hrono serve' running?". `client/http.py` maps
  every `httpx.HTTPError`, here `LocalProtocolError: Illegal header value`,
  to `Unreachable`, which sends the operator after a server that is up.
- **E6, note. Token in the log.** `hrono serve` prints the bootstrap token
  to stdout. Redirected to a log, the token sits in that file in clear.
- **E13, note. Server lifetime.** A server started from an agent's
  background shell dies with that shell's time limit. Run it under `nohup`
  or a service manager.
- **Recovery works.** After every restart the job left running by the dead
  worker was requeued and resumed. Condensations and briefs already stored
  were never paid for again.
