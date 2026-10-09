---
id: 185
title: the dashboard's triage view — what needs attention, and where it is
priority: medium
size: medium
depends_on: [180, 182, 183]
spec_refs: [build-order.md#T52]
---

## Context
T52: "Triage overview + worklist deep-links". The view that turns four read-only
pages into something an operator opens on purpose: not "here is your tree" but
"here is what is wrong with it".

## What counts as needing attention
Each of these is a state some earlier ticket learned to detect, and none of
them is visible anywhere today:

- **topics with no brief, or a stale one** (#064) — a topic recall cannot
  answer from.
- **chunks in no topic** (#086's incubator) — invisible to the map entirely.
- **topics nothing points at** (#124, #163) — a subtree out of the export, the
  defect that shipped twice.
- **forced members** (#113) — placements nobody scored.
- **runs that failed** — with their code and message (#161).

## Description
- `GET /ui/trees/{tree}/triage` — one line per kind, with a COUNT and a link
  that lands where the work is: the map opened on the right branch, the topic
  page, the runs page.
- A count of zero is stated, not hidden. "Nothing needs attention" is the
  answer an operator most wants and the one a blank page cannot give.

## Acceptance criteria
- [x] Each kind is counted, and links somewhere that shows the actual items.
- [x] A clean tree says it is clean rather than rendering an empty list.
- [x] An unreachable topic is listed — the defect that shipped twice is the
      one this view exists for.
- [x] Counts are per TREE (#054).
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-27 po: authored.

- 2026-09-27 dev: done, commit 1cecb4b. Five kinds, each counted per tree, each
  linking where the work is. Driven on a real tree: "nothing needs attention in
  default." with all five zeros still shown.

  **A zero is shown, never hidden.** That is the design of the page: an
  operator's most common question is "is anything wrong", and a list that
  renders nothing cannot distinguish "clean" from "broken query".

  **The root is not counted as unreachable.** It is meant to have no parent, so
  counting it would put every healthy tree permanently at 1 and teach people to
  ignore the row that exists to be noticed. The check runs over every level
  BELOW the top — which is #163's rule, reused rather than re-derived.

  Mutations: the root counted as unreachable -> 2 fail; a missing brief not
  counted -> 1; failed runs counted across every tree -> 1. And one that
  SURVIVED: checking only level 0 for orphans. My fixture's orphan was a LEAF,
  and in a two-level tree "every level below the top" and "level 0" are the
  same set — so the check looked right while only ever seeing leaves, which is
  precisely the blind spot #163 closed. The fixture is now three levels deep
  with an UPPER orphan, and the mutation fails two tests.

  Gate clean: 1293 passed, 2 skipped.

- 2026-09-27 qa: PASS, to po-review. Gate: 1293 passed, ruff clean. Drove the
  page against a real tree.

  The surviving mutation is the one worth recording, and it is the third time
  this month a two-level fixture has hidden an upper-level bug (#163's sweep,
  #163's guard, now this). **A two-level tree makes "all levels below the top"
  and "leaves only" indistinguishable.** That is a specific, repeatable trap,
  and it is not the same as the symmetric-fixture note already in
  CONTRIBUTING.md — it is about DEPTH, not shape. If it appears a fourth time
  it wants its own line.

  Everything else verified: per-tree counts, the clean statement, the zero
  rows, and the unreachable link landing on the topic itself rather than on a
  page you then have to search.

- 2026-09-27 po: CLOSED. Five views, and the dashboard now answers the question
  an operator actually arrives with.

  Every row on this page is a state some earlier ticket taught the system to
  DETECT and nothing ever taught it to SHOW. #086 has known about parked chunks
  since M3; #113 has flagged forced members since M7; #124 and #163 both
  shipped a defect whose entire signature is a row on this page. The detection
  was never the missing half.

  On qa's note: I agree it is distinct from the symmetric-fixture rule and I am
  not writing it down yet. Three instances, but all three are the same
  ticket-family (#163 and its descendants), so it may be one lesson rather than
  a pattern. A fourth from somewhere else makes it a rule.

  T54, T55, T56 and #184 remain in M10.
