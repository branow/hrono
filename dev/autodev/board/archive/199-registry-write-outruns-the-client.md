---
id: 199
title: registering a local model reports a timeout and then succeeds
priority: medium
size: small
depends_on: [168]
spec_refs: []
---

## Context
From #197. `hrono models set` on a local embedding model validates it by
LOADING THE WEIGHTS, which on a first load takes longer than the client's 10s
budget. The user sees "did not answer within 10s. It is running — the request
is just slow" — honest wording (#168 earned it) — for a write that landed. They
do not know whether to retry, and retrying a write that succeeded is how
someone ends up with two of something.

## Options
- A longer budget for registry writes specifically. A write that validates
  against a provider or loads a model is not a read, and one timeout for both
  is what makes this wrong.
- Or say what to do: "check with `hrono models list`".

The first is better if a number can be defended; the second is honest whatever
the number is.

## Review log
- 2026-09-28 po: authored from #197's walkthrough.
