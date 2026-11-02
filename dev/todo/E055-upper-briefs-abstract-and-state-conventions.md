---
id: E055
title: upper briefs describe every child and state shared conventions, and a brief that copies one child is caught
priority: high
kinds: [backend]
depends_on: []
outcomes: [O5]
journeys: [J9, J6]
waits_on: []
---

## Goal
An agent reading a level-2 or root brief today often gets one child's text
back (xgboost node 162, bcreg `hrono-v9.db` 467 and 468) and never learns
what the other areas do or which rules they share. After this epic every
upper brief above level 1 says what each child is for and how they hand work
on, plus a short Conventions part; a brief that still copies one child is
asked again and flagged. Moves O5 (E054 tickets 511, 521, 512; D1).

## Build on
- The seeded `brief-upper` prompt and its seeding path
  (`registry/seeding.py`, `summarize/brief_upper.py`); one prompt batch for
  511 and 521 (E051 and E052 in `dev/archive/` hold the measured wording).
- The existing retry-and-flag gate in `summarize/shape.py` (`brief_gate`,
  echo/talk-back checks, E015, E019): the copy check is one more rule there,
  not a new mechanism.
- Rejected: a separate "conventions" call per node (costs a call per upper
  node; E052 chose the prompt).

## Tickets

### 1 a level-2 or root brief describes every child at its own level and ends with Conventions
Change: the seeded `brief-upper` prompt (level 2 and above; level 1 keeps
its flows) asks for what each child area is for and how areas hand work on,
then a short Conventions part: each rule most children follow with its
condition, and each sibling that does the same job differently. The new
default re-seeds only where the user did not edit the prompt.
Done when:
- [ ] five replays of xgboost node 162 (stored tree, 5 real claude-code
      calls, D2) each name all seven children; the replies are in
      `evidence/E055/`
- [ ] a level-1 replay on the flask copy keeps its flow (diff of before and
      after in evidence)
- [ ] an edited `brief-upper` prompt in the registry is left as the user
      wrote it after upgrade
Look at: dev/archive/E051-upper-briefs-abstract.md,
dev/archive/E052-upper-briefs-state-conventions.md, docs/summarization.md

### 2 an upper brief that is mostly one child's text is asked again, then flagged
Change: after `brief-upper`, share of the brief's 6-word runs found in one
child's brief; over 30% asks once more, still over flags the brief (same
flag surface as the echo gate).
Done when:
- [ ] the check run offline over the stored trees flags xgboost node 162's
      original brief and bcreg `hrono-v9.db` nodes 467 and 468, and no
      level-1 brief (command and output in evidence)
- [ ] the flag shows on Health like the other brief flags
- [ ] docs/summarization.md states the rule and the 30% threshold

## Out of scope
- The bcreg rebuild that checks 511 at scale (Q3, human check).
- Unpinning xgboost node 162: the user's tree, the user's call.

## Tried

## Log
- 2026-11-02 po: created from E054 511, 512, 521 (O5, D1).
- 2026-11-02 po: plan approved (go); started, one at a time (battery, 3.5 GiB free).
