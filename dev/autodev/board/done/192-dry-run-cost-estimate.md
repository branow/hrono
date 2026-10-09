---
id: 192
title: the dry-run's cost half — calls and tokens, from measured history
priority: medium
size: medium
depends_on: [190, 179]
spec_refs: [build-order.md#T58, implementation-notes.md]
---

## Context
#178 split T58 because cost had no source of truth. #179 gave every job a token
record, and #190 shipped the impact half. This is what is left: turning "47
nodes would be re-briefed" into "and that is about this many calls and this
many tokens".

## Description
- `estimated_cost: {"brief_calls": n, "tokens": {"input": n, "output": n}}` on
  each affected tree in #190's response.
- Calls are exact — one per node to re-brief.
- **Tokens are projected from THIS install's measured history**, not from a
  constant: the mean input/output of the completions the same op recorded in
  past jobs (#179). An install with no history yet gets `"tokens": null` and a
  reason, never a made-up number.
- Still **no `usd`.** That needs a price per model, which is config this
  project does not have and which goes stale the moment a provider changes it
  (`summarize/spend.py` says so already). The spec's `usd` field waits for a
  price list nobody has asked for yet.

## Acceptance criteria
- [x] Calls match the node count the impact half reports.
- [x] Tokens are derived from recorded job spend, asserted against a planted
      history with a known mean.
- [x] No history means null and a reason, not a zero and not a guess.
- [x] No `usd` key at all.

## Review log
- 2026-09-27 po: authored as the cost half of T58, now unblocked by #179.
- 2026-09-27 dev: `impact.estimate`, attached to every row whose work is
  briefs.
  - The measurement is the `briefs` table's OWN `input_tokens` /
    `output_tokens`, not job results: one row per brief is a per-CALL
    measurement already, per tree and per level, with no dividing by a job's
    call count to get back to it.
  - Hand-written briefs (#156) record zero tokens because no model wrote them.
    They are excluded — averaging them in would quietly halve every estimate,
    in the direction that makes spending look cheaper.
  - No measured brief means `tokens: null` and a `basis` saying so. A zero
    would read as free.
  - No `usd`, and `summarize/spend.py` already says why.
  - Mutations, all killed: hand-written briefs averaged in; the mean not
    multiplied by the calls; no history reported as zero; the estimate taken
    across trees rather than per tree.
  - Driven live on :8797 with four briefs at 1200/1300/1400/1500 input tokens:
    the preview returns 5400 input for 4 calls, which is 1350 x 4.
  - Gate: 1393 passed, 2 skipped.
- 2026-09-27 qa: verified. `basis` is the part worth keeping: an estimate from
  two measured briefs and one from two hundred are different claims, and a
  bare number cannot tell them apart.
- 2026-09-27 po: accepted. T58 is complete, and with it every ticket M0-M11 in
  build-order except the parked hygiene items. The spec's `usd` field stays
  unfilled deliberately, and the reason is written down twice.
