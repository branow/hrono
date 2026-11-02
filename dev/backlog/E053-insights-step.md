---
id: E053
title: insights — a strong model reviews each large subtree and extends its upper brief with what the cheaper models cannot see
priority: medium
depends_on: []
requirements: []
---

## Goal
The tree states what the code says. A rule the code never writes down, a
rule older members of a family apply and newer ones dropped, a step that
breaks a correct result only when another step fails: none of these is in
any one section, so condense and brief cannot state them. A strong model
reading a whole subtree, with the lookups, can.

Measured on a private-corpus implementation eval (2026-11-01..02, kept
outside the repository; 36-topic unit, Opus as the reviewer):
- every review pass found 8-11 real issues no brief stated (claims sampled
  against the code were all true), and 3-4 statements in the briefs that
  the code proves wrong;
- cost fell from $3.96 to $2.43 per pass once the pass got its area brief and
  a one-line index of its topics up front and searched the condensations
  instead of reading them whole; the same unit's findings differ run to run
  (about 45 distinct issues over 7 passes, 8-11 per pass);
- extending the upper brief with the findings ($0.39 per brief) cut the
  implementing agent's turns (99 -> 86) and cost ($4.38 -> $3.46) on the
  same task, but not its score: the traps that agent still fell into were
  business rules absent from the code, which no review of the code can
  supply.

So the step is worth having for briefs that are true and complete, not as a
way to make a new feature correct. It is optional and off by default.

How it works (agreed 2026-11-02):
1. During `build-tree`, each node carries a counter: the brief characters
   below it that no insights pass has reviewed. A leaf's counter is its brief
   length; a parent's is the sum of its children's.
2. Right after `brief-upper` writes a node, and before its level is embedded
   and clustered into the next, a node whose counter reaches the tree's
   threshold (default 500k characters) gets one insights pass, and its
   counter goes to 0. Building continues upward; a higher node that reaches
   the threshold again gets its own pass, which reads the extended briefs
   below it. The root always gets a pass over what is left.
3. A pass has two calls. **Review**: an agent with the brief lookups (Read,
   Grep, Glob, Search over briefs, condensations and the source at its
   version), given the node's brief and a one-line index of its subtree up
   front, finds unwritten rules, siblings that disagree, rules older members
   apply that newer ones dropped, and invariants the code breaks; every
   finding cites the code it was confirmed in. **Extend**: one call that
   writes the findings into the node's brief, in the section where each
   belongs, correcting wrong statements in place and keeping the brief's
   structure. No separate file, section or page.

On the eval's 461-leaf tree the counter fires 6 passes (5 subtrees plus the
root).

## Tickets

### 531 an `insights` model role and a tree setting
Problem: there is no role for a strong model, and nothing to turn the step
on per tree.
Done when:
- [ ] a model role `insights` resolves like the others; setup offers the
  strongest model of the chosen provider for it, and the tree works with
  it unset
- [ ] a tree has `insights` (off by default) and `insights_threshold`
  (characters, default 500 000); the registry dry run reports the passes
  a change would cause and their estimated cost

### 532 build-tree runs a pass where the counter fires
Problem: the step has to sit inside the level loop, after a node's upper
brief and before that level is embedded, so the parent is clustered and
briefed from the extended brief.
Done when:
- [ ] on a tree with the setting on, each node whose unreviewed count
  reaches the threshold, and the root, get one pass; no other node does
- [ ] the parent of a reviewed node is clustered and briefed from the
  extended brief
- [ ] with the setting off, a build makes no insights call and produces the
  same tree as today

### 533 the review agent works on the existing lookups, cheaply
Problem: a pass that reads condensation files whole costs 50% more and
covers 4 of 36 topics.
Done when:
- [ ] the review runs on the lookup tools of `summarize/lookup.py`, read-only,
  with a turn cap
- [ ] the prompt (seeded, editable like the others) carries the node's brief
  and a one-line-per-topic index of its subtree, and tells the agent to
  search the condensations across all topics and read only what a hit
  points to
- [ ] each finding is stored with its evidence (file, lines, version), its
  confidence, where the brief stated it or should, and the hypotheses the
  agent checked and dropped

### 534 the extended brief is the node's brief, and its history says so
Problem: the reader of the tree must see one brief, while an operator must be
able to tell what the strong model changed and undo it.
Done when:
- [ ] the extend call replaces the node's brief text; the cheaper model's
  brief is kept as the previous version (brief versions, E033), and the
  version's provenance names the insights model and the pass
- [ ] a pinned brief (manual edit) is never overwritten: its findings are
  kept and shown, not applied
- [ ] the export renders the extended brief like any other; nothing in the
  export names the step

### 535 sync keeps the findings without paying for a new review each time
Problem: `sync-tree` rewrites a stale upper brief with the cheaper model,
which drops the extension; a new review on every sync would cost a pass per
change.
Done when:
- [ ] when a reviewed node's brief is rewritten, its stored findings are
  re-applied by the extend call; a finding whose evidence file changed
  version is not re-applied and is marked for the next review
- [ ] the unreviewed counter grows by the brief characters of the leaves
  that changed below a node; a node reaching the threshold again gets a new
  review on the next sync
- [ ] `settle` reviews the nodes the counter selects on the rebuilt tree

### 536 the dashboard shows the step
Problem: an operator needs to see what the strong model did, what it cost,
and turn it on or off.
Done when:
- [ ] tree settings have the on/off and the threshold, with the estimated
  passes and cost
- [ ] a reviewed topic's page says "extended by insights" with the model and
  date, shows the change against the cheaper brief (the versions diff), and
  lists the findings with their evidence, the checked-and-dropped list
  folded
- [ ] the usage page counts the `insights` role like the others

## Open questions (Orest decides before 532)
- The threshold: characters of leaf briefs (as measured) or of all briefs
  below; and its default.
- One review per pass, or two in parallel (the findings of two passes over
  the same unit overlapped by only 3 of 17).
- Whether 535's re-apply is enough, or a changed subtree should always get a
  new review.

## Relation to E052
E052 asks the upper brief prompt to state shared conventions and sibling
differences. The insights step finds those with the code in hand; E052 is
the cheap version for every upper brief. Decide both in the same prompt
batch.

## Log
- 2026-11-02: proposed from the private-corpus experiment (seven review
  variants, two implementation re-runs with the findings); integration
  design agreed in conversation.
