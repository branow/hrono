# a claude-code text model cannot be registered through the API

What: `PUT /models/<name>` for a `kind: text` model whose connection is a
`claude-code` connection always fails with `bad-request: model connection
rejected the request`. `registry/validation/model_validation.py`
`_default_generate` has no claude-code branch: it builds an HTTP URL from the
connection's `endpoint` (which a claude-code connection does not have) and
POSTs `chat/completions` to it.

Where: src/hrono/registry/validation/model_validation.py, `_default_generate`.

Why it matters: the README recommends claude-code as the way to try hrono out,
and the first step after the connection (`hrono models set`) refuses every
model. Found by E004 while building hrono's own tree on a scratch server
(2026-10-03); worked around there by inserting the model rows directly, which
is how the demo homes got theirs too.
