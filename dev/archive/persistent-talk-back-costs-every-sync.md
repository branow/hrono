# A section the model always talks back to costs two calls on every sync

What: since E001 (f3e4853) `update` runs condense whenever a stored
condensation talks back. If the re-condense is refused again (`answer`
retries once, `keep` never caches a refusal), the old talk-back stays stored,
so every later sync, even over an unchanged corpus, spends 2 LLM calls per
such section, indefinitely, and the list never empties.

Where: src/hrono/tree/update.py `_talked_back`; src/hrono/summarize/condense.py
`keep`.

Fix to decide (PO): e.g. record the refusal (attempt count / last tried) and
skip a section already refused for the same body and model on a no-op run,
leaving it listed for the operator.
