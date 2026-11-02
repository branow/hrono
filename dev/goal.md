# Goal contract

Written by the PO from the user's goal; checked by qa on every epic and by
the acceptance agent before the run is done. Builders never edit it.

Run goal: we need integrate new step 'insights' and do minor fixes

## Purpose
An admin of a large tree can turn on an optional, off-by-default step in
which a strong model reviews each large subtree with the read-only lookups
and writes what no single section states into that subtree's upper brief.
An agent reading the tree then finds the unwritten rules, sibling
differences and wrong statements fixed in the brief it already reads. The
design is E053 (`dev/archive/E053-insights-step.md`, agreed 2026-11-02),
now tickets 531-536 of `dev/backlog/E054-tree-explains-the-architecture.md`.
The minor fixes are E054's small tickets (D1).

## Outcomes
Pass/fail, on the real app (the flask bench copy, PROJECT.md "Run the real
app"), as an admin or curator uses it. `asked`: from the user's words.
- O1 (asked) An admin sets an `insights` model role (setup offers the
  chosen provider's strongest model; every role works with it unset) and,
  per tree, `insights` (off by default) and `insights_threshold`
  (characters, default 500 000), from the CLI registry and from the
  dashboard's tree settings. The registry dry run states the passes the
  change causes and their estimated cost. With the step off, a build makes
  no insights call and writes the same tree as before this run.
  Evidence: the dry-run output on the flask copy with the step on; a test
  comparing an off build with today's, zero `insights` ledger rows.
- O2 (asked) With the step on (threshold lowered so at least one subtree
  below the root fires on flask), `settle` on the flask copy gives one pass
  to each node whose count of unreviewed brief characters below it reaches
  the threshold, and to the root, and to no other node. Each pass is one
  read-only review on the `summarize/lookup.py` lookups with a turn cap,
  then one extend call. Each finding is stored with its evidence (file,
  lines, version), confidence, where the brief should state it, and the
  hypotheses dropped. The extended text is the node's brief, the cheaper
  brief is its previous version with provenance naming the insights model
  and pass, and the parent is clustered and briefed from the extended brief.
  Evidence: the job's log and stage counts; the findings rows; the brief
  versions of one reviewed node; at most 10 real model calls (D2).
- O3 (asked) The step survives edits and syncs. A pinned (hand-edited)
  brief is never overwritten: its findings are kept and shown, not applied.
  When a sync rewrites a reviewed brief, that node gets a full new pass in
  the same sync before its parent; a node whose count first reaches the
  threshold on a sync gets its first pass. The export renders the extended
  brief like any other and never names the step.
  Evidence: a commit synced into the flask copy; `hrono tree export` grep
  for "insight" empty; tests for pin and re-pass.
- O4 (asked) A curator sees the step in the dashboard: tree settings show
  on/off, threshold, estimated passes and cost; a reviewed topic's page says
  "extended by insights" with the model and date, shows the versions diff
  against the cheaper brief, and lists the findings with their evidence,
  the dropped hypotheses folded; Usage counts the `insights` role like the
  others. Copy uses GLOSSARY.md words (new words added there).
  Evidence: screenshots of the settings, a reviewed topic and Usage at 390
  and 1440 wide, light and dark, on the flask copy after O2.
- O5 (asked, minor fixes) Upper briefs abstract and do not copy one child:
  at level 2 and the root the `brief-upper` prompt describes every child at
  its own level (511) and adds a short Conventions part: rules most
  children follow and siblings that differ (521); an upper brief that is
  mostly one child's text (over 30% of its 6-word runs) is asked again and
  flagged if it still copies (512).
  Evidence: the copy check run offline over the stored trees flags xgboost
  node 162's original brief and bcreg `hrono-v9.db` nodes 467 and 468, and
  no level-1 brief; five replays of xgboost node 162 cover all seven
  children (5 real calls).
- O6 (asked, minor fixes) `update` condenses new sections before placing
  them, so incremental placement reads the same vector as a build (506),
  and TAU (0.70) is re-checked on that vector space.
  Evidence: a commit synced into the flask copy places its new sections by
  their condensation; the TAU check's numbers in docs/evaluations.

## Quality bars
- Step off: zero insights calls, same build time and tree as today.
- A pass on a ~36-topic subtree costs about $2.50 or less metered (measured
  $2.43 on Opus); the turn cap bounds it.
- Fast suite stays under its 90 s budget; full suite green.
- Dashboard pages touched: no horizontal scroll at 390 wide, keyboard
  reachable, light and dark.

## Non-goals
- A separate insights file, section or page in the tree or export
  (decided 2026-11-02: the findings extend the brief in place).
- Verifying E054 501-505 (grouping; code in since 56c718e, 1086985): it
  needs the bcreg rebuild, which runs only on Orest's go (Q3).
- Recall quality; business rules absent from the code.

## Assumptions
Each is a decision in decisions.md.
- "Minor fixes" means E054 tickets 506, 511, 512 and 521 (D1, Q1).
- qa may spend at most 10 real claude-code subscription calls per epic on
  the flask copy and the stored xgboost/bcreg trees (D2, Q2).
- Seeded review and extend prompts come from the generic recipe of the
  private experiment, with no private data in the repository (D3).

## Human checks
- The bcreg rebuild and the `tree-L3` agent runs and 36-question suite
  (E054 "How to check"), on Orest's go.
- Insights measured on a corpus whose leaves disagree on a rule (the
  private corpus, run in `~/hrono-private`, kept out of git).
- One pass on a metered Anthropic key, to confirm the cost the dry run
  estimated.
