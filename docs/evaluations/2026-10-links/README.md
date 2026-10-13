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
