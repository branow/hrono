---
id: E051
title: upper briefs abstract over their children instead of copying one
priority: high
depends_on: []
requirements: []
---

## Goal
High upper briefs (level 2 and the root) sometimes copy one child's brief
almost word for word instead of summarizing all their children. Found on the
xgboost cold build (`docs/evaluations/2026-10-xgboost/README.md`, Notes): the
root's brief was its first child's (the static demo data), so `root.md`
opened with "Static demo and test data". The code passed the right input,
all seven child briefs. Replaying the same prompt twice gave one real
summary and one copy, so the model does this on its own.

The suspected cause is the `brief-upper` prompt. It asks every upper level
for end-to-end flows that name the part, the function and the record's
state at each step. That fits a level-1 area. At the top of a whole
repository the children are unrelated areas (core, bindings, JVM, CI,
tests), and the one child whose brief already reads like flows with
functions gets reproduced. The prompt pulls the upper levels down to code
detail instead of letting them abstract.

## Tickets

### 511 the brief-upper prompt abstracts at higher levels
Problem: one `brief-upper` prompt serves every level above the leaves, and
asks each of them for function-level flows.
Done when:
- [ ] a level-2 or root brief describes all its children at their own
  level of abstraction: what each area is for and how the areas hand work
  to one another, not the functions inside one area
- [ ] replaying the xgboost root input (node 162) five times gives five
  briefs that cover all seven children
- [ ] level-1 briefs keep their flows (no regression on bcreg's level-1
  briefs)

### 512 a brief that copies one child is caught
Problem: `brief_gate` rejects only refusals and prompt echoes, so a copy is
stored without anyone noticing.
Done when:
- [ ] an upper brief with two or more children whose text is mostly one
  child's (for example, over 30% of its 6-word runs) is rejected and asked
  again, and flagged if it still copies
- [ ] the check flags xgboost node 162's original brief and BC Registries
  `hrono-v9.db` nodes 467 (97% of child 446) and 468 (55% of child 466), and
  no level-1 brief of either tree

## Log
- 2026-10-25: found on the xgboost build. The xgboost root was replaced by
  hand with the good replay (pinned; text in
  `~/hrono-xgboost/root-brief-replay0.md`). Unpin node 162 once 511 lands
  so the fixed prompt rewrites it.
