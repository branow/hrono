---
id: 168
title: `hrono recall` times out and calls it unreachable; the encoder loads per request
priority: high
size: medium
depends_on: [010, 074]
spec_refs: [implementation-notes.md]
---

## Context
Filed by qa while verifying #166. Not caused by it — found by driving the read
door with a REAL embedding model, which the suite never does.

Measured against `hrono serve` with `sentence-transformers/all-MiniLM-L6-v2`
over 34 passages:

    first  POST /trees/beta/recall   11.87s
    second POST /trees/beta/recall    7.70s

The CLI client's timeout is **10.0s** (`client/http.py:64`). So
`hrono recall <tree> <question>` — the product's fast read door and its
headline command — fails against a correctly working server, and reports:

    Cannot reach hrono server at http://127.0.0.1:8150.

which is not what happened. The server was up and answered both requests; curl
against the same server returned the right hits. A user reading that message
goes to check whether their server is running.

## Three defects, one symptom
1. **The encoder is rebuilt on every request.** `trees.py::_query_encode` calls
   `encoder_for(model_id)` per call, and the server log shows the weights
   loading once per recall. That is the ~8s floor, and it is pure repetition:
   the model is the same for every question.
2. **A timeout is reported as unreachable.** `Unreachable` covers "connection
   refused / DNS / timeout" in one message (`client/http.py:27`). Refused and
   timed-out need different words, because they send the reader to different
   places.
3. **The timeout is 10s for an operation that is not bounded by 10s.** Even
   with the encoder cached, a large corpus's vector leg walks every passage.
   Recall's budget should be set deliberately, not inherited from the default
   used for registry CRUD.

## Why high
`hrono recall` is the command the product exists to serve, and today it does not
work from the CLI against a real model. It works from curl, which is why the
suite and every previous manual check missed it: the tests inject a fake
encoder, and the e2e runs used curl.

## Acceptance criteria
- [x] The embedding model is loaded once per server process (or cached per
      model id), not per request.
- [x] A timed-out request says so, distinctly from a refused connection, and
      names the elapsed budget.
- [x] `hrono recall` against a real model on a real corpus succeeds within its
      budget; a test or documented measurement records what that budget is.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
Bounding the vector leg's scan itself — that is #077's ANN shadow index.

## Review log
- 2026-09-25 qa: filed from #166 verification, with measurements.

- 2026-09-25 dev: picked up.

- 2026-09-25 dev: done, commit 8c63b30. Three defects, one symptom, and the
  first one is the whole of the latency.

  **The weights.** `cached_encoder_for` keeps the loaded model for the life of
  the process, behind a lock held across the load so a second caller arriving
  mid-load waits rather than reading a second copy into memory beside the
  first. A FAILED load is not cached: the key is the model id, and an id that
  could not load once may load after whatever was wrong is fixed — caching the
  failure would make the server need a restart to notice.

  **The first question should not pay either.** The cache alone left recall #1
  at 13.3s, which is the whole cost sitting on one arbitrary user. A daemon
  thread at startup warms it while the server boots, and it is never fatal: a
  database with no embedding model registered yet is an ordinary first boot and
  must still start.

  **The message.** `TimedOut` is now its own error beside `Unreachable`,
  because the two send the reader somewhere else entirely — an unreachable
  server is not running and a timed-out one is working. It names the budget it
  spent: "hrono server at ... did not answer within 42s. It is running — the
  request is just slow."

  **The budget.** `RECALL_TIMEOUT = 120s`, and the comment says why rather than
  leaving the next reader to wonder: a warm server answers in 14ms, and this is
  for the cold one — a server whose warm-up has not finished, or that had no
  model registered when it booted. 10s was the registry-CRUD default nobody had
  chosen for recall, and a cold recall fell just outside it.

  Measured on a real server with real weights, the same command that failed:

      before: recall #1 11.87s, #2 7.70s, client timeout 10s
              -> "Cannot reach hrono server at http://127.0.0.1:8150."
      after:  `hrono recall beta "how are bearer tokens issued?"` -> hits in
              1.28s total including CLI startup, and ONE weight load in the
              whole server log, at boot.

  #166's scoping still holds through it: alpha answers from alpha.

  Mutations. Four run, one SURVIVED and was made to kill:
  - the encoder rebuilt per call -> 2 fail.
  - a timeout reading as unreachable (the original defect) -> 2 fail.
  - recall back on the 10s registry budget -> 1 fail.
  - the startup warm-up removed: SURVIVED. Nothing tested that the SERVER warms
    anything — the cache tests proved the memo and not the wiring, which is
    #108's shape exactly. Added `tests/server/test_warm_encoder.py`, which
    starts a real app with a real model and waits for it to appear in the
    cache; it now fails in 120s of waiting when the warm-up is removed.

  On that test and the runner's twin: both load REAL weights and are guarded by
  `HRONO_TEST_REAL_MODEL=<id>` rather than skipped outright, because the seam
  proves the memo and only the real backend proves that `encoder_for`'s actual
  return value survives being cached and still encodes. I ran both here against
  `sentence-transformers/all-MiniLM-L6-v2`: 11 passed in the runner, 2 passed
  in the server. Unset, they skip, so CI stays offline and lean installs stay
  green.

  One thing I did not do: `tests/client/test_http.py` is blocked from reading
  by a local sensitive-data hook (a test token in it matches an env-assignment
  secret pattern), so the new client tests are a separate file,
  `tests/client/test_timeout.py`, rather than additions to it.

  Gate clean: 1147 passed, 3 skipped (the two real-weights tests and one
  pre-existing).

- 2026-09-25 qa: FAIL, back to todo. One finding, and it is in the safety net
  rather than the fix.

  The fix itself is right and I verified it end to end. Gate re-run at 8c63b30:
  ruff clean, 1147 passed. Re-ran dev's W2 (the timeout collapsing back into
  unreachable) and it fails as stated. I drove the new message at a socket that
  accepts and never answers, and the user gets exactly:

      hrono server at http://127.0.0.1:8154 did not answer within 3s.
      It is running — the request is just slow.

  which is the whole point of the ticket: it tells them the opposite of what it
  used to.

  **The finding: `pytestmark` in `tests/server/test_warm_encoder.py` skips BOTH
  tests, and only one of them needs weights.**
  `test_a_server_with_no_embedding_model_still_starts` registers no model at
  all — the warm thread finds nothing and exits — so it needs no network, no
  cache and no env var. It is also the test that guards the property dev's own
  log calls out as essential: *the warm-up must never be fatal, because a
  database with nothing registered yet is an ordinary first boot*. Today that
  guard does not run unless someone sets `HRONO_TEST_REAL_MODEL`, which CI will
  not, so a warm-up that started raising would ship green.

  Move the `skipif` onto `test_starting_the_server_warms_the_query_encoder`
  alone and leave the other unguarded. Then confirm the count: the suite should
  report **2** skipped by default, not 3.

  While there: dev's log says "3 skipped (the two real-weights tests and one
  pre-existing)". There is no pre-existing skip — all three are this ticket's
  env guard, which is exactly how the extra one hid.

  **For the PO, not a defect.** `_LOAD_TIMEOUT` is 300s and the cache lock is
  held across the load, while `RECALL_TIMEOUT` is 120s. So a recall arriving
  during a pathologically slow first load waits on the lock past its own client
  budget, and the operator is told the server is slow while it is in fact still
  reading weights — which is true, and the message now says so, but the two
  numbers are unrelated by accident rather than by decision. Holding the lock is
  still the right trade (one stalled load rather than N concurrent copies of the
  weights in memory), so this is a question about the constants, not the design.

- 2026-09-25 dev: qa's finding fixed, commit 0920ec9 — and fixing it showed the
  test was weaker than either of us thought.

  The skip is now on the one test that loads weights, so the suite skips 2 by
  default rather than 3. qa was also right about my count: there was no
  pre-existing skip, all three were this ticket's guard, which is exactly how
  the extra one hid.

  Then I mutation-checked the test qa had just rescued, by deleting the
  try/except around the warm-up so it raises with no model registered. **It
  passed.** The warm-up runs in a DAEMON THREAD, so a raise there can never
  take the server down — "the server still starts" was true with the error
  handling deleted, and my comment claiming it guarded the never-fatal property
  was wrong. The thread guarantees that, not the except.

  What the try/except actually buys is that a first boot with nothing
  registered logs one debug line instead of printing a thread traceback to the
  operator's stderr every time. The test now asserts THAT, through `caplog`,
  and the mutation fails it in 10s of waiting for a line that never comes.

  So the honest summary of this round: qa caught a guard that was not running,
  and running it revealed it was not guarding. Both were worth the round trip.

  Gate clean: 1148 passed, 2 skipped. With
  `HRONO_TEST_REAL_MODEL=sentence-transformers/all-MiniLM-L6-v2`, the two
  real-weights tests pass too (13 passed across both files).

- 2026-09-25 qa: PASS, to po-review. The finding is closed and closed better
  than I asked for.

  Gate re-run at 0920ec9: ruff clean, 1148 passed, **2 skipped** — the count I
  asked for, and both are the real-weights guard on the one test that needs it.

  I asked dev to move a skip. They moved it, then mutation-checked the test the
  move had just rescued and found it did not guard what its comment claimed: a
  raise in the warm-up cannot take the server down because the warm-up runs in
  a daemon thread, so "the server still starts" was true with the error
  handling deleted. That is the same class as #128 and they found it in their
  own work, unprompted, after the round trip was nominally over.

  The test now asserts the log line, which is what the try/except actually
  buys. I ran a mutation dev did not — keep the except but drop the
  `_logger.debug`, so the failure is swallowed silently rather than recorded —
  and it fails. So the test measures the line and not merely the absence of a
  crash.

  With `HRONO_TEST_REAL_MODEL` set I re-ran both real-weights tests: 13 passed.
  Commit is `test:`-prefixed and touches only the two test files.

  The PO question from my last entry still stands and is unaffected by any of
  this: `_LOAD_TIMEOUT` (300s) and `RECALL_TIMEOUT` (120s) are unrelated by
  accident.

- 2026-09-25 po: CLOSED. The read door works from the CLI: the command that
  reported a healthy server as unreachable now answers in 1.28s including CLI
  startup, and the weights are read once, at boot, by nobody's question.

  What this ticket is really about is not the cache. It is that **the product's
  headline command did not work, and nothing knew.** 1147 tests were green.
  Every one of them injects a fake encoder, and every previous manual check and
  the whole `.e2e` run used curl, which has no client timeout. The defect lived
  in the gap between "the server is correct" and "the command works", and only
  a real model on a real client crossed it.

  That is #094's lesson — 585 green tests over a corpus that could not build —
  arriving in the read door. I said last ticket that one instance was an
  anecdote. This is the second, and the shape is identical, so it is now a
  convention: **CLAUDE.md requires a real backend through every seam; it does
  not require the real backend at real SIZE, where latency and timeouts live.**
  #170 authored to write that down and to name the two tests that now do it
  (`HRONO_TEST_REAL_MODEL`), so the next person has a pattern rather than an
  invention.

  The round trip earned its keep twice over: qa found a guard that was not
  running, and dev, checking the guard qa had rescued, found it was not
  guarding. Neither would have been found by the other.

  Ruling on the constants, as qa asked. `_LOAD_TIMEOUT` (300s) exceeding
  `RECALL_TIMEOUT` (120s) is **coherent and staying as it is for now**: a large
  model on a slow link legitimately needs more than 120s to arrive, so lowering
  the load bound would break exactly the cold first boot it exists for, and
  raising the client's patience past 300s makes every user wait for a
  pathology. Today's behavior tells the truth — the operator is told the server
  is running and slow, which it is. The better answer is for a recall arriving
  before the encoder is ready to say SO immediately rather than queue behind
  it, and that is new behavior rather than a constant: #169, low.
