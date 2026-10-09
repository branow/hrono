# The update stage hides what its condense step did

What: `tree/update.py` `update` runs `condense` but `_outcome` returns only
`{"changed", "batch"}`. On E001's e2e a sync over an unchanged tree spent 4
condense calls (re-doing talked-back condensations) and the run record's
`update` stage said `{"changed": false, "batch": null}`; the spend shows only
in the job's `usage.calls`. No `condensed`, `refused` or `tokens` per stage,
contrary to #179 ("an op that calls a model says what it spent").

Where: src/hrono/tree/update.py `update` / `_outcome`.

Fix: fold condense's outcome (condensed, refused, tokens) into the update
stage result when it ran.
