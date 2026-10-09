---
id: 170
title: convention — a seam's real-backend test must run at real SIZE, not only really
priority: medium
size: small
depends_on: [108, 168]
spec_refs: []
---

## Context
Authored by the PO after #168, as the second instance of one shape.

CLAUDE.md already says: a ticket that introduces a SEAM must carry at least one
test that exercises the REAL backend through that path, "even at a trivial
size", because a seam proves the wiring and cannot prove the backend's
contract (#094, #108).

#168 is that rule's blind spot. Every recall test injects a fake encoder, and
the one real-backend test in `tests/embed/test_runner.py` deliberately loads no
weights "to keep CI offline". Both were correct by the rule as written. The
result was that `hrono recall` — the product's headline command — did not work
at all against a real model, for an unknown length of time, with 1147 tests
green. The cost was ~8s per request against a 10s client timeout: a number that
exists only at real size, on a real backend, through a real client.

The same shape appeared one ticket earlier (#166), where a defect could not be
shown with a fixture small enough to write inline because the confidence gate
correctly refuses a tiny corpus.

## What to write down
Extend the seam convention in CLAUDE.md: where a backend's cost or its
statistics are part of its contract — model loading, clustering thresholds,
recall's confidence gate — the real-backend test must run at a size where that
cost or statistic is real, and the measurement must be recorded in the ticket.

Name the pattern that now exists, so it is reused rather than reinvented:
`HRONO_TEST_REAL_MODEL=<id>` guards `tests/embed/test_runner.py::test_the_cache_
holds_a_REAL_encoder` and `tests/server/test_warm_encoder.py::test_starting_the_
server_warms_the_query_encoder`. They skip on a lean or offline install and run
on a machine that has the weights.

## Acceptance criteria
- [x] CLAUDE.md carries the extension, in the voice of the existing rules.
- [x] It names the env-var pattern and where to find the two examples.
- [x] It says what must be RECORDED (the measurement), not only what must run.

## Review log
- 2026-09-25 po: authored from #168's review, as the second instance of #166's
  shape.

- 2026-09-26 dev: done. Two bullets in CLAUDE.md, beside the rules they extend
  and in the same voice.

  The first is the ticket: where a backend's COST or STATISTICS are part of its
  contract, the real-backend test runs at a size where they are real and the
  NUMBER goes in the ticket. It says what "even at a trivial size" does and
  does not buy, cites the two instances, and names the env-var pattern so the
  next person inherits it rather than inventing one.

  The second I added unasked, because writing the first one made it obvious. We
  have now had four surviving mutations this month and every one was a finding
  about where the guard actually sits, not a formality:

  - a fixture too SYMMETRIC to show the asymmetry it claimed (#166: both trees
    had identical corpora, so the combined median equalled each half's);
  - a population of ONE with no distribution to change (#166 again, the keyword
    leg, where each tree matched a single passage);
  - a unit test proving a FUNCTION while nothing proved its caller (#163: the
    sweep could have run `range(1)` forever with the collector's own tests
    green);
  - a property held by something ELSE entirely, so deleting the code under test
    changed nothing (#168: a daemon thread already made the warm-up non-fatal;
    #158's merge, where the transaction and not the ordering prevented a
    half-write).

  The existing rule says a surviving mutation means "not yet a tooth". It does
  not say the survivor is itself information, and each of those four cost a
  round of guessing before anyone asked WHY it survived.

  **One thing the ticket could not fix.** `CLAUDE.md` is gitignored — its own
  header says local-only, never committed — so this convention exists on one
  machine and in no history. Nothing to commit here, and nothing for a fresh
  clone to read. Whether the durable conventions belong in a file the repo
  actually carries is a question above this ticket; flagging rather than moving
  them.

  Gate clean (no source changed): ruff clean, 1160 passed, 2 skipped.

- 2026-09-26 qa: PASS, to po-review. I verified the two bullets say what the
  tickets they cite actually found, since a convention that misquotes its own
  evidence is worse than none:

  - the `HRONO_TEST_REAL_MODEL` guard names two files, and both exist and skip
    by default (`pytest -rs` reports exactly those two);
  - the "~8s per request against a 10s client timeout" figure matches #168's
    measurements (11.87s / 7.70s, client budget 10.0);
  - all four surviving-mutation shapes in the second bullet are in the tickets
    it cites, with the right ticket against each.

  The second bullet was not asked for and earns its place. The existing rule
  tells you a survivor means the test is not a tooth; it does not tell you the
  survivor is INFORMATION about where the guard really sits, which is the part
  that cost a round of guessing four times this month.

  **Dev's flag is the real finding and it is bigger than the ticket.**
  `CLAUDE.md` is gitignored by its own instruction, so every convention this
  board has learned — the seam rule, mutation-checking, the fixture rule
  (#144), and now these two — exists on one machine and in no history. A fresh
  clone, or anyone else, gets none of it. That is not a defect in #170, which
  did exactly what it was told; it is a question about where durable
  conventions live, and it belongs to the PO.

- 2026-09-26 po: CLOSED. The convention is written where the rule it extends
  lives, and the second bullet dev added unasked is the better of the two — it
  turns four separate round-trips into one instruction.

  **On qa's finding, and it is the right question:** `CLAUDE.md` says of itself
  "local-only working memory... must never be committed. Anything meant to be
  shared belongs in the repo's real docs, not here." By that rule the
  conventions are in the wrong file, and have been for a while. The seam rule,
  mutation-checking, the fixture rule (#144), the URI decision, the baked
  constants — none of that is working memory. It is how this codebase is built,
  it was learned expensively, and today it survives exactly as long as one
  working copy.

  #171 authored to move the durable conventions into a committed doc and leave
  `CLAUDE.md` the pointer it describes itself as. I am authoring rather than
  doing: which file, and what the repo's public docs should say, is a
  stakeholder's call about the project's shape — not something to settle inside
  a ticket about test sizing.
