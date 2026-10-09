---
id: 169
title: a recall arriving before the encoder is ready should say so, not queue
priority: low
size: small
depends_on: [168]
spec_refs: [implementation-notes.md]
---

## Context
From #168's qa review and the PO ruling on its constants.

The query encoder is warmed at boot and cached behind a lock held across the
load. A recall arriving mid-load therefore WAITS for it, which is the right
trade against reading a second copy of the weights into memory — but the wait
is bounded by `_LOAD_TIMEOUT` (300s) while the CLI's patience is
`RECALL_TIMEOUT` (120s), so a pathologically slow first load spends the user's
whole budget queued behind something they cannot see.

Today they are told the truth ("the server is running, the request is just
slow"), which is why this is low rather than a defect.

## The better answer
A recall that finds the encoder still loading returns immediately with a
distinct, honest status — the model is still being read, try again — instead of
occupying a threadpool thread for as long as the load takes. That also removes
the only path by which enough concurrent recalls could exhaust the pool while
the server is otherwise healthy.

## What it needs
- A non-blocking way to ask the cache "is this model ready", distinct from
  "load it".
- A status and message for it that is not confused with a timeout or an
  unreachable server (#168 established that those three are different things
  and that saying the wrong one sends the operator to the wrong place).
- Leave the blocking path for the OPS, which have no user waiting and should
  keep waiting for the weights.

## Acceptance criteria
- [x] A recall issued while the encoder is loading returns promptly and says
      what is happening, rather than blocking on the load.
- [x] Once warm, recall is unchanged (measured: 14ms).
- [x] The embed ops still wait for the model rather than declining work.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-25 po: authored from #168's review.

- 2026-09-26 dev: done. `ready_encoder_for` returns the encoder if it is
  already in the cache and otherwise None — and the None is not a dead end: the
  miss STARTS the load, which is what makes "come back shortly" true rather
  than hopeful. The ops keep calling `cached_encoder_for`, which still blocks,
  because an op has nobody waiting and should not read a second copy of the
  weights.

  `start_loading` needs its OWN short-lived lock. `_CACHE_LOCK` is held for the
  duration of a load, so asking it "is one already running" would have been
  exactly the blocking this ticket exists to remove — the in-flight set answers
  that question in microseconds instead.

  It also simplified #168: the startup warm-up was its own thread and is now
  one call to `start_loading`. One loader, so a question arriving mid-boot
  joins the load already running rather than starting a second.

  Driven on a real server, a recall issued two seconds after boot and again
  twenty seconds later:

      503 {"code":"unavailable","message":"the embedding model is still
           loading (sentence-transformers/all-MiniLM-L6-v2); recall will
           answer once it is in memory"}
      200 in 0.42s

  Three distinct answers now where there was one: unreachable (nothing there),
  timed out (working, slow), and unavailable (working, not ready yet). #168
  established that saying the wrong one sends the operator to the wrong place.

  On the seam: `ready_encoder_for` and `start_loading` take a `build`, which
  replaced a monkeypatch of `cached_encoder_for` in my first draft — DI over
  monkeypatching, and the test reads better for it. The REAL backend goes
  through `start_loading` on every boot, so
  `test_starting_the_server_warms_the_query_encoder` covers it with real
  weights under `HRONO_TEST_REAL_MODEL`.

  Mutations, all killed: recall queueing instead of reporting -> 1 fail; a
  ready encoder reported as not ready -> 2; a second caller starting a second
  load -> 1.

  Gate clean: 1167 passed, 2 skipped.

- 2026-09-26 qa: FAIL, back to todo. The feature works and the ticket's own
  case is right — a recall two seconds after boot says "still loading" and one
  twenty seconds later answers in 0.42s. What it does to a model that will
  NEVER load is a regression, and it is the more common operator mistake.

  Driven against a registered model id of `totally/not-a-model`, three recalls
  six seconds apart:

      attempt 1: 503 "the embedding model is still loading (totally/not-a-model);
                      recall will answer once it is in memory"
      attempt 2: 503 the same
      attempt 3: 503 the same

  Forever, and the sentence is FALSE — nothing is loading; three failures are
  sitting in the server log where the operator cannot see them. Before this
  ticket that same typo answered `embed-error: embedding model failed to load`,
  which #161 had just made visible. We have taken a diagnosable failure and
  made it indistinguishable from a slow start.

  It is also the #132 family in a new place: reporting a state that is not the
  one the system is in. "Still loading" is the one message an operator will
  wait on rather than act on.

  And my own concern about the test: `test_a_recall_before_the_model_is_ready_
  says_so` uses `not-a-real-model-id` and asserts 503. It is currently the only
  test of this path, and it ENSHRINES the wrong answer — it would keep passing
  through any fix that distinguishes the two cases. That test needs to become a
  test of a genuinely cold-but-loadable model, or of the failure case with the
  right expectation.

  **What must change.** Remember the last load FAILURE per model id, and let
  `ready_encoder_for` tell its caller which of the two states it is in — never
  loaded yet, or tried and failed with this reason. Recall then answers 503
  "still loading" for the first and the real `embed-error` for the second. The
  retry behaviour can stay: a failure that has been reported may still be
  retried, since a model can start working once the operator fixes what was
  wrong.

- 2026-09-26 dev: qa's regression fixed. They were right on both counts, and
  the second one is the sharper.

  **The behaviour.** `_FAILED` remembers the last load failure per model id,
  and `ready_encoder_for` raises it rather than returning None. Same bad model,
  same three attempts:

      before: 503 "still loading (totally/not-a-model)"  x3, forever
      after:  500 embed-error "embedding model failed to load:
              totally/not-a-model"                        x3

  The retry is untouched — a remembered failure does not stop the loading, it
  stops the lie — and a model that recovers clears its own entry, which a test
  pins. Three answers stay distinct: unreachable, timed out, still loading, and
  now failed-with-a-reason.

  **The test.** qa's point that my own test ENSHRINED the wrong answer is the
  one I should have caught: it reached 503 by ARRIVING FIRST, so it would have
  kept passing through any fix that told the two states apart. Both route tests
  now seed the state they mean — `_INFLIGHT` for loading, `_FAILED` for failed
  — so neither can pass by winning a race, and neither starts a real load.

  Mutations, both killed: the failure not raised, i.e. the regression restored
  -> 3 fail; a recovered model keeping its old failure -> 1 fail.

  Gate clean: 1170 passed, 2 skipped.

- 2026-09-26 qa: PASS, to po-review. The regression is closed and the test that
  enshrined it is now a test of the thing it names.

  Gate at 41c5382: ruff clean, 1170 passed. Drove the CLI against the same
  unloadable model that produced my finding:

      $ hrono recall default "anything"
      embedding model failed to load: totally/not-a-model

  One line, the model id in it, and the operator knows what to fix. That is the
  whole distance travelled: "still loading", forever, to that.

  Ran one dev did not — drop the `_INFLIGHT` half of the start guard so only
  the cache is checked, which would spawn a fresh loader on every request
  during a slow load. `test_a_second_caller_does_not_start_a_second_load`
  fails, so the thread count is really guarded and not incidentally right.

  On the seeding in the route tests: I asked for determinism and dev seeded the
  module's own `_INFLIGHT` and `_FAILED`. That reaches into private state,
  which I would normally push back on — here it is the right call, because the
  alternative is a test that reaches its answer by winning a race, which is the
  defect I filed. The seeding also keeps a real HuggingFace fetch out of the
  suite, which matters more.

  Three answers are now distinct at the read door, and each sends the operator
  somewhere different: unreachable (nothing there), timed out (working, slow),
  still loading (working, not ready), failed (working, and here is why). #168
  established why that matters; this finishes it.

- 2026-09-26 po: CLOSED. The read door now has four answers where it had one,
  and each sends the operator somewhere different.

  This ticket shipped a regression and caught it in the same session, which is
  the process working rather than failing — but the regression is worth naming
  because it is a shape we will meet again. A fix that makes the COMMON case
  better ("still loading" instead of a silent queue) made the UNCOMMON case
  worse, and the uncommon case — a mistyped model id — is the one an operator
  actually hits. Making something honest about the state it is in requires
  knowing all the states it can be in.

  qa found it by asking what happens to the input nobody intends to give, and
  then noticed that dev's own test reached the right answer by ARRIVING FIRST.
  A test that wins a race passes through the fix for the bug it was meant to
  cover. That is a fifth shape for the surviving-mutation list in CLAUDE.md,
  and unlike the others it did not survive a mutation — it was found by
  reading. I am not adding it yet; one instance.

  Low was the right priority and it is now done, which is the argument for
  clearing small things when the lane is empty rather than letting them mature.
