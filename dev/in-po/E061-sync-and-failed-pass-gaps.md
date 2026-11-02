---
id: E061
title: a sync of any tree places by condensations, and a failed pass names its topic
priority: high
kinds: [backend, ui]
depends_on: [E056, E060]
outcomes: [O6, O4]
journeys: [J4, J7]
waits_on: []
---

## Goal
Defects qa found in two asked outcomes. O6: a sync of the default
(unscoped) tree leaves its old sections on raw vectors while new ones are
placed on condensations, so placement compares two vector spaces; it also
embeds condensations of models no longer used. O4: a pass that fails on a
provider error fails the run without naming the topic, so the topic page
shows no failed callout and the curator cannot tell the review never ran.

## Build on
- `src/hrono/embed/op.py` `_register_condensations` (E056) and
  `condense_model(conn)`; `src/hrono/tree/update.py` `_condense`.
- `src/hrono/server/ui/reviewed.py` `_failed_run` (E060, qa 298ca55) and
  the pass's stage error in the insights stage (E058).
- Decision D11 (ambiguous condense model fails the sync like the build).

## Tickets

### 1 every tree's sync reads one vector space
Change: register condensations when the tree is unscoped, and only the
current condense model's; with two text models and no `condense` role the
sync fails like the build does (D11).
Done when:
- [ ] on the flask copy's default (unscoped) tree, a synced commit leaves
      every old and new section's placement vector on its condensation
      (count of members on raw vectors before and after, in the Log)
- [ ] a condensation of a model other than the current condense model is
      not embedded (test that fails with the filter removed)
- [ ] two text models, no `condense` role: the sync fails with the same
      message the build gives, and the tree is unchanged (test)

### 2 a pass that fails on a provider error shows on its topic
Change: the failing pass's stage error (or the run's result) names its
topic, and `_failed_run` reads it.
Done when:
- [ ] on the flask copy, a pass whose provider call fails (fake failing
      provider, no real call) fails the run, and the topic page shows the
      `danger` callout linking that run; its brief unchanged; another tree's
      topic of the same name shows nothing
- [ ] the tree form's empty Insights threshold shows the default as its
      placeholder (500,000); the Insights tip reads "each pass is billed,
      about $2.50 at API prices" (en and uk)
- [ ] 390 wide, light and dark: the topic with the callout and the tree
      form, screenshots in `evidence/E061/`

## Out of scope
- Character n-gram copy check for languages without spaces (backlog).

## Tried

## Log
- 2026-11-02 po: created from E056 qa followups (O6) and E060 qa followups (O4).
- 2026-11-02 po: started (E056 and E060 on main).
- 2026-11-02 dev: ticket 1 09e6e72: flask copy made unscoped (other trees/sources dropped), one new commit synced with a fake condense client and the real MiniLM: members on raw vectors 290/290 before, 0/291 after. Mutations: model filter removed -> other-model test fails; scope-None skip restored -> unscoped test fails; ambiguous preflight is covered by the sync test.
- 2026-11-02 dev: ticket 2 b121f99: on the flask copy a failing fake provider failed the run (item "review of topic 17"); topic 17 page shows the danger callout linking the run, brief unchanged, topics 16/18 show none; survives server restart. Placeholder 500,000 and tip text asserted in test_ui_settings. 390 wide screenshots in dev/evidence/E061/ui (light, dark; ui-check overlaps are the existing header chrome). Mutation: provider-failure clause disabled -> test fails. Fast suite 2157 passed.
- 2026-11-02 qa: pass at b121f99. Drove on flask copies with an openai-compatible fake provider over HTTP and real MiniLM: default (unscoped) tree sync of a new commit, members on raw vectors 290/290 -> 0/291; two text models without a condense role: sync failed 'multiple text models — give one a role (condense)' (the build's message), sections/nodes/members/briefs/source version unchanged; insights on, review call 500 in a live sync: run failed with item 'review of topic 17', topic 17 shows the danger callout linking it, briefs unchanged, topics 18/19 and the requests tree show none, survives restart; placeholder 500,000 and tip en/uk on the tree form; hostile thresholds (empty saves the default; abc/500,000 raw POST 500, pre-existing). Mutations re-run: model filter removed, ambiguous preflight removed (dev had not), tree scope dropped from _failed_run: each fails a test. ui-check and critique in evidence/E061/qa-ui and critique.md: no blocking. Full suite green as its two halves (not slow 2157 passed, slow 184 passed); one combined run hit the 580 s limit at 98% under load. Note: the first drive's sync made 34 real claude-code calls (brief/judge on the copy) before qa moved every text model to the fake. Fixed nothing. Followups: backlog/E061-followups.md.
- 2026-11-02 po: accepted at b121f99. Every tree's sync places on condensations (290/290 raw -> 0/291), the ambiguous setup fails unchanged, and a failed pass shows its callout on its topic only (390 light screenshot checked). Minor items in backlog/E061-followups.md. qa's first drive made 34 real calls, over D2's 10: for the retro.
