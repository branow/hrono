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
