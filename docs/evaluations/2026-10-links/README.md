# Links from condensation: pilot

Can condensation name what a section connects to, so a mechanical step can
link tree pages? v3 tree (`~/hrono-eval/db/hrono-v3.db`), the v3 `condense`
prompt plus a REFERENCES request, Haiku through `claude -p --json-schema`.
11 sections: the fee-waiver chain across the three services, a listener, a
test, two docs, an OpenShift template. Cost $0.64.
`harness/condense_links.py`, raw answers in `pilot.json`.

- **Structure is reliable.** 11 of 11 calls returned schema-valid JSON
  (`structured_output`); no parsing needed.
- **The references are mostly the wrong kind.** 1-11 per section, but most
  name the chunk's own imports, enums, models, loggers and decorators
  (`HTTPStatus`, `logger.error`, `Business (model)`). The real hand-offs
  are there when the chunk has one: the legal API's invoice section names
  `PAYMENT_SVC_URL` with "POST ... receives JWT bearer token". The docs
  give good ones (FAS doc: Pay_API -> CFS_API).
- **Embedding a reference does not find its target.** Cosine against leaf
  pages sits at 0.85-0.97 for everything, so the top page is often the
  section's own or a look-alike in another service (`PAYMENT_SVC_URL` ->
  the legal API's own page first, pay-api third; `Role` -> auth-web
  helpers). It works when the name is distinctive (`updateFilingData` ->
  the filing mixin page, 0.98).

## The claude CLI against the Agent SDK

`harness/bench_sdk.py`, Haiku 4.5 pinned, the same three prompts per arm,
sequential (`bench.json`):

| arm | seconds | output tokens | cost | schema met |
|---|---|---|---|---|
| CLI, hrono's flags | 33 / 59 / 30 | 3.1k / 6.5k / 3.1k | $0.025 / 0.047 / 0.024 | 2 of 3 |
| CLI, `--tools ""` | 391 / 95 / 113 | 11k / 10k / 13k | $0.057 / 0.054 / 0.066 | 3 of 3 |
| Agent SDK, `tools=[]` | 118 / 38 / 60 | 13k / 4k / 6k | $0.073 / 0.024 / 0.034 | 3 of 3 |

- The Agent SDK runs the same CLI: it spawns a `claude` binary it bundles.
  Unpinned, that bundled CLI resolved "haiku" to Haiku 5.5, not 4.5.
- The CLI's fixed overhead is about 33k tokens of tool definitions, read from
  cache ($0.003 at Haiku prices). Removing tools removes it, but it is not
  where the time or money goes.
- Output dominates, and most of it is thinking: 0.9k-6.6k thinking tokens
  for one section, varying run to run. That variance, not CLI against SDK,
  sets the time and the cost.
- `--json-schema` checks the answer after it is written and asks again on a
  miss; at `--max-turns 3` one CLI call ended without the structured output.

## Round 2: references across the edge, matched by name

`harness/links2.py`, the same 11 sections, Agent SDK, thinking off: $0.14
for all 11 (round 1: $0.64), 4-20 s a call. Matches in `links2.txt`.

- **The request now says what not to list** (own functions, libraries,
  types, enums, models, constants, logging) and asks for the most specific
  name the content gives, a direction, and what passes with its conditions.
  Docs and listeners now give real edges: the entity filer's NATS subject and
  GCP topic with their payloads, the FAS doc's ten CFS endpoints, the legal
  API's POST to `PAYMENT_SVC_URL` with "Bearer token from the JWT header;
  staff or system roles add routingSlip, bcolAccountNumber, datNumber". The
  RBAC template rightly gives none. Code chunks still list calls into their
  own repository (`PaymentService.create_invoice`), which are links too.
- **Matching by names, rare ones weighted up.** Every identifier-like name in
  the target and the payload (snake_case, camelCase, dotted, paths; plain
  words left out) is looked up in the full-text index; each votes
  1/(pages holding it) for those pages. The legal API's payment call lands on
  the pay-api schema and service pages (2nd and 3rd; 1st is a legal-API
  sibling page), because the payload's field names live on both sides. The
  filer's event subject lands on the entity emailer, its consumer.
  `updateFilingData` and `PaymentService.create_invoice` land on their
  definitions. `LegalServices.fetchFiling` does not reach the legal API.

## Stage 3: a slice condensed with links, its briefs rebuilt

`harness/slice.py`, outputs in `slice/`. Every section of a file cited by
three hard questions (fee waiver, payment notification, two payment
listeners): 100 sections, 21 leaf pages. Condensed with references (Haiku
4.5, SDK, thinking off, $1.22, 97 of 100 schema-valid), 364 links by rare
names (a page that refers to the same target is a co-caller and is skipped;
mostly-test pages are not link ends), then the 21 leaf briefs rebuilt with the
v3 `brief` prompt, a CONNECTIONS block and a 7th point asking for them
(Sonnet, thinking off, $1.79). A Sonnet judge says, per fact (22), whether
the pages holding its files state it:

| pages | yes | partial | no | score |
|---|---|---|---|---|
| v3 briefs | 1 | 21 | 0 | 0.52 |
| briefs with connections | 2 | 19 | 1 | 0.52 |
| v3 condensations of the fact's own files (ceiling) | 1 | 21 | 0 | 0.52 |

- **The connections are written.** The legal API page now says "Pay
  service: the caller's Bearer token is forwarded"; the payment listeners'
  pages name each other's subjects.
- **Nothing moves, not even the ceiling.** Even the notes of the exact cited
  files score "partial" on 21 of 22 facts. What is missing is never a piece:
  each fact is a conclusion drawn across pieces ("so the payment service sees
  the customer", "a second delivery of a PAID-but-unapplied filing resets the
  completion date and resends the email") or an exact list ("which filing
  types get no waiveFees"). The pieces are on the pages; the conclusions are
  in no single source, so no summary of a source states them.
- **Details the notes keep, the briefs drop.** Both condensations of
  `get_filing_types` say the header's waiveFees is copied into each fee line;
  no brief keeps it (300-900 words over 30-50 sections).
- **This judge cannot steer the work.** A fact-level yes/partial/no saturates
  at "partial" for every arm, ceiling included.
