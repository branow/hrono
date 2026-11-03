# E063 followups (qa round 1)
- A review that fails on a provider error during `settle` (Review now, `hrono tree review`) is not shown on the topic page: `_review_due` (src/hrono/tree/settle.py:126) runs `review.run` outside a stage, so the failed job has no `error_details.item` and `_failed_run` (src/hrono/server/ui/reviewed.py:172) never matches. Fix: run it as a named stage, as sync does, and test a 500 from the insights model through the topic page.
- `details:not([open]) > :not(summary) { display: none; }` (src/hrono/server/templates/base.html:221) hides closed-disclosure text from the browser's find-in-page, which Chromium otherwise auto-expands. Fix: scope the rule to the tree menu and Runs, or use `content-visibility`/`hidden=until-found`.
- The "low" confidence chip (`plain`) looks like plain mono text, and the chip shows the model's English word on the uk page (templates/node.html:156). Fix: a faint wash for `plain`, and translate high/medium/low.
- `POST /jobs {"op": "settle", "tree": "<unknown>"}` succeeds on a tree that does not exist (src/hrono/server/jobs.py); the CLI now checks first, but the endpoint should refuse it like `/trees/<name>/sync` does.
- The insights threshold has no upper bound; a 40-digit value is saved (src/hrono/registry/collections/trees.py:69). Harmless today, but a `le=` bound would give a field error.
- (po) Topic 18 in uk at 390 shows the failed-review callout and, under it, "Перегляд не знайшов, що додати." (templates/node.html:146): the two read as a contradiction. Show "found nothing to add" only when the last review finished.

(po 2026-11-03: all six folded into E065.)
