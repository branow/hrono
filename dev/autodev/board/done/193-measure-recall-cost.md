---
id: 193
title: measure what a recall actually costs, and record the numbers
priority: medium
size: small
depends_on: [075, 166]
spec_refs: [build-order.md#M11]
---

## Context
#077 (the ANN shadow index) is parked behind its own trigger: "pull in when
recall latency is MEASURED as a problem or M11 hardening". Nobody has measured.
Building an index whose subtle risk is the z-floor's semantics over a candidate
set, on a suspicion, is the wrong order.

Two of #077's three premises also need re-checking against the code as it is
now:

- "a recall holds the #008 connection" — `Database.connect` lends from a
  connection POOL now, and the database is in WAL (`db/connection.py`), so a
  reader does not hold the writer out.
- "the scan serializes against the single writer" — same answer, unless the
  measurement says otherwise.

What is certainly still true is the third: `vector_leg.scores` walks every
passage in scope, reads two vectors per passage, and does three pure-Python dot
products over them. That is the number to get.

## Description
A measurement, not a fix. Plant corpora at several sizes with realistic vector
dimensions, time `vector_leg.scores`, and record:

- wall time per recall at each size, and whether it grows linearly;
- how long a recall holds its connection, and whether a concurrent write is
  delayed by it;
- where the time goes — the vector reads or the arithmetic.

Then rule on #077 with numbers in hand, and write the numbers into it.

## Acceptance criteria
- [x] Timings at a minimum of three corpus sizes, recorded in this ticket.
- [x] A measured answer on whether a recall delays a concurrent write.
- [x] A measured split between fetching vectors and scoring them.
- [x] #077 updated with the numbers and re-ruled (pulled in, re-parked with a
      threshold, or closed).
- [x] Any test added is guarded so it does not slow the normal suite.

## Review log
- 2026-09-27 po: authored. #077's trigger is a measurement nobody has taken,
  and two of its three premises predate the connection pool.
- 2026-09-27 dev: measured on this machine (arm64 macOS, python 3.13),
  planted corpora of random unit vectors at **384 dims**, timing
  `vector_leg.scores` with no tree scope.

  | passages | wall  | per passage |
  |---------:|------:|------------:|
  |      500 | 0.073s|    0.146 ms |
  |     2000 | 0.299s|    0.149 ms |
  |     8000 | 1.203s|    0.152 ms |

  **Linear, at 0.15 ms per passage per query.** Extrapolating: 20k passages
  ~3s, 200k ~30s. A real model at 768 or 1024 dims multiplies that by 2-2.7.

  **Where it goes, at 8000 passages:** fetching vectors 0.82s, arithmetic
  0.53s. But the fetch is not the database — replacing every per-passage query
  with ONE bulk read of the whole `embeddings` table and blending in memory
  took 0.76s to 0.64s, a 16% saving on that half and ~9% overall. The cost is
  **pure-Python vector arithmetic**: one 768-wide `combine` and three dot
  products per passage, in interpreted loops.

  **Concurrency: not a problem, and #077's premise is obsolete.** A write
  issued in the middle of a 1.2s recall waited **7.7 ms**. `Database.connect`
  lends from a connection POOL and the database is in WAL
  (`db/connection.py`), so a reader has not held the writer out since #008's
  single connection was replaced.

  **The 18x that is not an ANN index.** The same arithmetic in numpy — stack
  the vectors, one matrix-vector product — takes **0.066s** where the Python
  loops take 1.215s at 8000 passages. Identical math, no candidate set, no
  approximation, nothing to re-derive about the z-floor. That is #194.
- 2026-09-27 qa: verified the numbers reproduce across runs (three runs, the
  per-passage figure moved by under 5%). The measurement that matters most is
  the negative one: the write waiting 7.7 ms is what retires half of #077's
  case, and it was worth taking before building anything.
