---
id: E057
title: an admin turns insights on for a tree and sees which topics it will review and what that costs
priority: high
kinds: [backend]
depends_on: []
outcomes: [O1]
journeys: [J3, J10]
waits_on: []
---

## Goal
An admin of a large tree wants a strong model to review its big areas, but
only knowingly: it is off by default and costs about $2.50 a pass. This
epic adds the `insights` model role and the per-tree `insights` (off) and
`insights_threshold` (500 000 characters) settings, the per-topic count of
unreviewed brief characters that decides which topics get a pass, and a
registry dry run that states the passes and their cost before anything
runs. No pass runs yet (E058). Moves O1 (E054 ticket 531 and the counter
of 532; design in `dev/archive/E053-insights-step.md`).

## Build on
- Tree settings are the pydantic `Tree` model in
  `registry/collections/trees.py` (like `lookups`); the dashboard's Settings
  form renders its fields, so the fields land there for free (E060 adds the
  estimate beside them).
- Roles: `registry/completeness.py` `BUILD_ROLES`/`SYNC_ROLES`; `insights`
  is optional and never makes the registry incomplete. The model registry
  and `role` validation in `registry/collections/models.py`; setup's model
  step offers the provider's strongest model for it (claude-code: Opus;
  anthropic: the current Opus id; openai: its top model), unset by default.
- Dry run: `?dry_run=true` and `registry/impact.py` already return a
  change's impact; add passes and estimated cost to it. Cost basis from the
  research: about $2.43 per pass plus $0.39 extend on Opus metered,
  subscription marked an estimate as Usage does (`dev/research/insights-recipe.md`).
- Counter: derive it from stored briefs and pass records (characters of
  every brief below a topic written since that topic's last pass; a pass on
  a child takes its subtree out of the parent's count), rather than a stored
  number that can drift. The pass table (node, time, model, version) is made
  here, empty, so E058 only writes rows.
- Rejected: a timer or a separate op to pick topics; the counter is read
  where briefs are written (E058) and by the dry run.

## Tickets

### 1 the insights role and the two tree settings
Done when:
- [ ] `hrono registry` (models, trees) accepts role `insights` and tree
      fields `insights` (default off) and `insights_threshold` (default
      500 000, positive integer); a bad value is refused in plain words
- [ ] every role still works with `insights` unset; completeness never
      asks for it; setup offers the strongest model of the chosen provider
      for it and lets it be skipped
- [ ] docs/api.md, docs/summarization.md and GLOSSARY.md (new word
      "insights": the step, in glossary words) say what these are

### 2 which topics a pass would review, and the dry run says so
Done when:
- [ ] on the flask copy with `insights` on and the threshold lowered so at
      least one topic below the root qualifies, `PUT /trees/<t>?dry_run=true`
      (and the CLI) lists the topics that would get a pass (always the
      root), how many, and the estimated cost with its basis
- [ ] with the step off, the dry run says no passes and $0
- [ ] a unit test of the counter: a leaf counts its brief, a parent the sum
      of what is unreviewed below it, a pass resets the subtree

## Out of scope
- Running a pass (E058); the dashboard estimate (E060).

## Tried

## Log
- 2026-11-02 po: created from E054 531-532 (O1).
- 2026-11-02 dev r1: T1 21d66ca, T2 same commit; real flask copy: CLI --dry-run off says no passes $0, on at 60000 lists topics 17 (level 1) and root, $5.64; threshold 0 refused; settings survived server restart. Mutations: ignore child pass in counter, drop always-root: tests fail.
- 2026-11-02 qa r1: pass at 88fd21d. Drove on the flask copy: CLI and HTTP dry run off (no passes, $0) and on at 60000 (topics 17, 19, $5.64), after a pass row on 17 (root only, $2.82), with a claude-code insights model (subscription estimate in basis); hostile thresholds (0, -5, "many", 1.5, null, 1e30, "") refused 422 by field; role typo refused; dashboard form toggles on/off and refuses 0; settings survive restart; planner 0.12 s on a 20k-leaf tree. Re-ran mutation (child pass ignored: 4 fail). Fixed: f455a74 setup refilled a cleared insights field on retry, babab38 test for the subscription estimate, 88fd21d Ukrainian for the two tree-setting tooltips. Full suite green (2264). Followups: dev/backlog/E057-followups.md.
- 2026-11-02 po: accepted at 88fd21d. The role, the two settings and the dry run hold on the flask copy; followups folded into E058 (no model, root re-pass, D8) and E060 (tip copy, bool threshold).
