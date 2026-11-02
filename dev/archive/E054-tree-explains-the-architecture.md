---
id: E054
title: the tree explains the architecture — grouped by what code does, briefs that abstract, state conventions, and a strong-model review of large subtrees
priority: high
depends_on: []
requirements: []
---

## Goal
On a large unknown corpus an agent reading the tree must find how the system
works: one service in one branch, a flow stated top down, upper briefs that
abstract over all their children and name the rules they share, and the
rules no single section states, found by a strong model. Merged on
2026-11-02 from E050, E051, E052 and E053 (in `dev/archive/`, with their
full logs and evidence); one prompt batch and one rebuild serve all of it.

Estimate (from the board's history, not a guess): the loop built E033–E049,
2–6 tickets each, in 15–60 minutes of wall time per epic. This epic has 18
tickets: about 4–6 hours of loop time. The rebuilds dominate: the xgboost
cold build took 1 h 16 min; the bcreg rebuild is larger and runs only on
Orest's go. Insights review costs about $2.43 per pass on Opus, about 6
passes on a 461-leaf tree.

## Tickets

### From E050: grouping and briefs (code in: 56c718e, 1086985; unverified)
- 501 core code is not clustered with build, test and fixture files: on
  `bcreg`, each file of `lear-filings-1` and `pay-3` sits in a leaf titled by
  its service; no leaf mixes product code with tests, fixtures, Docker, Make or CI.
- 502 one service sits under one top-level branch; a file's sections are not
  spread over unrelated groups.
- 503 root plus at most 2 briefs below it give the components and order of
  the `lear-filings-1` flow.
- 504 the pay-api account leaf states the account-lock concept in one or two
  sentences; boilerplate takes at most a line per brief.
- 505 given root alone an agent picks the right branch for `lear-filings-1`
  and `pay-3`; no title or node URI is meta text or a licence header.
- 506 `update` condenses new sections before placing them (today incremental
  placement reads raw content); TAU (0.70) is re-checked for the new vector space.

### From E051: upper briefs abstract
- 511 a level-2 or root brief describes every child at its own level (what
  each area is for, how areas hand work on); replaying xgboost node 162 five
  times covers all seven children every time; bcreg level-1 briefs keep their flows.
- 512 an upper brief that is mostly one child's text (over 30% of its 6-word
  runs) is rejected and asked again, flagged if it still copies; flags
  xgboost 162 and bcreg `hrono-v9.db` nodes 467, 468, and no level-1 brief.
  Unpin xgboost node 162 once 511 lands.

### From E052: conventions
- 521 the `brief-upper` prompt asks for a short Conventions part: each rule
  most children follow, with its condition, and each sibling that does the
  same job differently. On a tree whose leaves disagree, the area brief names
  both variants and the leaves carrying each.

### From E053: insights (optional, off by default)
- 531 a model role `insights` (setup offers the provider's strongest model;
  works unset) and per-tree `insights` (off) and `insights_threshold`
  (default 500 000 characters); the registry dry run reports passes and cost.
- 532 build-tree keeps a counter per node (characters of every brief below
  it not yet reviewed); after `brief-upper` writes a node whose counter
  reaches the threshold, and always the root, it gets one pass and the
  counter resets; the parent is clustered and briefed from the extended
  brief; with the setting off, no insights call and the same tree as today.
- 533 the review runs read-only on the lookups of `summarize/lookup.py` with
  a turn cap; its seeded, editable prompt carries the node's brief and a
  one-line index of its subtree and searches condensations rather than
  reading them whole; each finding stores evidence (file, lines, version),
  confidence, where the brief should state it, and the dropped hypotheses.
- 534 the extend call replaces the node's brief; the cheaper brief is the
  previous version, with provenance naming the insights model and pass; a
  pinned brief is never overwritten (findings shown, not applied); the export
  never names the step.
- 535 when a sync rewrites a reviewed brief, that node gets a full new pass
  in the same sync, before its parent; a node whose counter first reaches the
  threshold on a sync gets its first pass; `settle` reviews what the counter selects.
- 536 tree settings carry on/off, threshold, estimated passes and cost; a
  reviewed topic says "extended by insights" with model and date, the
  versions diff and the findings with evidence; Usage counts the role.

## How to check
- One rebuild of `bcreg` after 511, 512 and 521 land (on Orest's go); trace
  `lear-filings-1` and `pay-3` plus 2–3 others through
  `hrono tree export bcreg --levels 3`; a few agent runs with the harness in
  `docs/evaluations/2026-10-bc-registries-agents/` (`tree-L3` arm), then the
  36-question suite.
- Insights measured on a corpus whose leaves disagree on a rule.

## Out of scope
- recall quality (tested separately)

## Log
- 2026-11-02: E050–E053 merged into this epic (Orest).
- 2026-11-02 po: split into E055 (511, 512, 521), E056 (506), E057 (531, counter of 532), E058 (532-534), E059 (535), E060 (536); 501-505 wait for the bcreg rebuild (D4, Q3), tracked in backlog/bcreg-rebuild-checks.md.
