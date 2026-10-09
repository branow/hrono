---
id: 213
title: a run page that says what happened, what failed, and lets you retry
priority: high
size: big
depends_on: []
spec_refs: [REQUIREMENTS.md#6 (39, 40, 44)]
---

## Context
A 6m30s successful `maintain` shows "It reported nothing" and "No result recorded". A failed one shows `llm-error: claude-code refused the call: error_max_turns` and nothing else. The most expensive action in the product leaves no account of itself.

## Description
Every op records a result: the composite ops (`maintain`, `sync-tree`, `build-tree`) record what each stage did — files read, sections cut, condensations written, topics formed, briefs written or kept — and the run page shows the stages as a timeline with status, duration and counts. If `maintain` runs its stages in-process without child jobs, it still reports them.

A failure names the stage, the item it was working on (which section or topic), the error in plain words, and the next step: for the known error codes write a human sentence and a remedy; keep the raw error behind a disclosure.

Retry: a failed or cancelled run can be re-run with the same parameters from its page. Work already done is not paid for twice (condensations are cached by content hash; say so on the button).

A finished run shows what changed in the tree: topics added, removed, re-filed, briefs rewritten, linking to the activity log.

The runs table: one line per run, the description only on hover or on the run page, progress and spend filled in (#203 supplies spend), consistent headers, filter by status and op, paging.

## Findings from the UI review (2026-10-03)
Seen by driving the dashboard in headless Chromium against a copy of the local test database (tree `click`: 8 topics, 2 levels, 126 sections, 3 runs), as admin and reader, at 1440px and 800px, light and dark. Screenshots are in `.autodev/board/ui-review-2026-10-03/`. Severity: **A** wrong or broken, **B** confusing enough to cost time, **C** polish. The tree is small, so anything that only breaks at scale was not seen; forms were opened, not submitted.

- **A** A 6m30s successful `maintain` shows "It reported nothing" and "No result recorded": no stages, no counts, no tokens. The most expensive action in the product leaves no trace. Screenshot: `s-run-ok.png`.
- **A** A failed run shows `llm-error` / "claude-code refused the call: error_max_turns" and nothing else: not which stage, not which section, not what to do, no retry. Screenshot: `admin-run-1440-light.png`.
- **B** Each row repeats the op's full description, so the table is mostly the same two sentences; PROGRESS and TOKENS columns are empty.
- **B** Three column headers are orange and three grey with no visible reason.
- **B** The op descriptions shout ("the NORMAL one", "the FIRST one").
- **C** "One stage at a time" lists 14 ops with identical Run buttons and no guard or order hint beyond the hint bubble.

## Acceptance criteria
- [ ] a successful `maintain` on a real repo shows per-stage counts and durations — driven end to end, not a constructed row
- [ ] a failed run shows stage, item, plain-language cause and next step; the raw error is still available
- [ ] each error code the pipeline can raise has a human sentence, and a test fails when a new code has none
- [ ] retry re-enqueues with identical parameters and the page says what will not be redone
- [ ] the runs table has one row height, filters by status and op, and pages
- [ ] a run in flight updates live without reload, as today

## Out of scope
Job priorities (#050). Scheduling.

## Review log
- 2026-10-03 po: authored from the requirements review and the UI review of the same day, at the user's request.
- 2026-10-03 dev: started.
- 2026-10-03 dev: done in bfb9f75. STAGES: `jobs/stages.py` — `Stages.run(op, call, over=)` times each stage and keeps its result; `maintain` and `sync-tree` now return `{..., "stages": [{op, over, seconds, result}], "tree": {...}}` (maintain used to return None: "It reported nothing"). A raising stage becomes `StageFailed(stage, item, cause, outcome)`; the worker stores the finished stages as the failed job's result, the CAUSE's code (llm-error, cluster-error...) and `details.stage` / `details.item`. The item comes from the exception: `pool.mapped(named=...)` notes which item a failed call was for — condense names "section <path>", brief/brief-upper "topic <id>". WHAT CHANGED: `tree/changes.py` snapshots topics, filing and brief timestamps before the first stage and diffs after the last: topics added/removed, sections re-filed, briefs written (sentences in outcome.py, linked to the activity log). FAILURE IN WORDS: `server/failures.py` — every error code hrono defines has a sentence and a next step; `test_every_error_code_has_a_sentence` imports every hrono module and walks every AppError/DomainError subclass (killed by deleting one entry). The run page shows "Failed at <stage>, on <item>", the sentence, the remedy, and the raw `code: message` behind a disclosure. RETRY: `POST /ui/jobs/{id}/retry` re-enqueues (or re-fans-out) the same op, scope and tree, started_by the retrier; writer for maintain/sync-tree, admin for any other stage (403 otherwise); the button says condensed/embedded work is reused. RUNS LIST: one line per run (description on hover), headers all alike (the orange ones were `.when` colliding with a global class), status and op filters, 25 per page with Newer/Older, tokens from the #201 ledger (in incl. cache / out), "at <stage>" on failed rows; descriptions no longer shout; "one stage at a time" is numbered in pipeline order. Live SSE updates unchanged. Not done here: spend in money on the list (#203's). Tests (tests/server/test_runs_explained.py, maintain through the REAL Worker): success records 8 stages with seconds and counts and topics added; a broken clusterer fails with cluster-error, stage cluster, and the 4 stages before it kept; a model failing on one file fails with llm-error, stage condense, item "section f4.txt"; run page shows stage, sentence, remedy, raw error, timeline and retry; retry re-runs the same op/scope/tree as the retrier; a writer cannot retry an admin stage; list pages (25+5), filters by status and op. Updated: runs-list tests (error detail moved to the run page; plain headers), maintain/sync-chain tests (StageFailed names the stage and carries the finished ones). Mutations, all KILLED: worker drops the failed outcome; stage missing from details; pool notes no item; no role check on retry; status filter ignored; a code's sentence removed; maintain drops the tree diff. Real browser (Chromium, writer): a maintain that failed on f4.txt, then a clean one, on the same tree — the failed run page reads "Failed at condense, on section f4.txt | A call to the language model did not come back with an answer. | Check the model and its connection in Settings, then retry…"; the clean run's timeline shows condense "1 section condensed" — the other 8 were reused from the failed run, which is the retry promise measured; "Run it again" landed on a new maintain run page. Screenshots .autodev/board/evidence/213/{runs-list,run-ok,run-failed}.png. Gate: clean, 1685 passed.
- 2026-10-03 qa: KICKBACK (one finding, seen on a real run). Gated bfb9f75 in a worktree (import path asserted inside it, bytecode off): ruff format --check clean, ruff check clean, pytest 1685 passed / 4 skipped. Drove it in Chromium on a copy of the local test database, worktree server. Works: runs list one line per run, plain headers, status filter (failed -> 2 rows), op filter, tokens "—" for pre-ledger runs; a PRE-#213 failed run degrades well ("Failed" + the llm-error sentence + remedy, no stage); reader sees no retry button and a forged `POST /ui/jobs/{id}/retry` as the reader -> 403; as a WRITER "Run it again" -> new maintain job with op/scope/tree identical (`maintain`, `{}`, `click`) and started_by `wri`. That retry then failed FOR REAL (claude-code `error_max_turns` re-condensing docs/changes.md, 4 condense calls in the ledger, 2 failed) and the page named it correctly: "Failed at condense, on section docs/changes.md", sentence, remedy, raw error behind the disclosure, stage timeline sync/split/embed done + condense failed. Screenshots in evidence/213-qa/ (213-real-failed.png).
  FINDING — on that same failed run the "What it did" card says "Nothing to change. Everything this run looked at was already up to date. A re-run over unchanged sources makes no model calls at all." That is false on its face: the run FAILED, and it made 4 model calls. Cause: this ticket now stores a failed run's finished stages as its result (`{"stages": [{sync, result: null}, {split, result: null}, {embed, result: null}]}`), and `outcome.read` treats a result with no counts as `quiet`, so src/hrono/server/templates/run.html:115-119 (`{% elif job.outcome.quiet %}`) fires for a failed run. Before bfb9f75 a failed run had no result and fell to "It reported nothing". Fix: never show the "Nothing to change / no model calls" state for a run whose status is failed or canceled — say what finished before the failure (the timeline already does) or nothing; and add a test over a failed run whose completed stages reported nothing, asserting that text is absent, mutation-checked by removing the status guard.
  Note, not blocking: sync, split and embed record `result: null` and render "nothing to do" on this run; on an unchanged tree that is true, but check that on a FIRST build they report what they did (files read, sections cut), since AC 1 asks for per-stage counts; and the runs list still renders every root job of the tree before slicing a page (src/hrono/server/ui/jobs.py jobs_view), which is fine at 3 runs and will not be at thousands.
