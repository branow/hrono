# Decisions

What the PO decided for you, why, and how to undo it. Newest last.

- D1 2026-11-02: "minor fixes" in the run goal means E054's small tickets:
  506 (update condenses before placing), 511 (upper briefs abstract), 512
  (copy check) and 521 (Conventions part). Why: they sit in the epic you
  merged with insights on 2026-11-02 to share one prompt batch, and each is
  small and checkable without a rebuild. Replaces: nothing (the goal named
  no fixes). Undo: answer Q1 b or c.
- D2 2026-11-02: qa verifies with real model calls, at most 10 per epic,
  on the claude-code subscription, on the flask bench copy and the stored
  xgboost/bcreg trees; never a rebuild. Why: a pass checked only on a fake
  model is not a check, and your pilot rule caps a first run at 10 calls.
  Undo: answer Q2 b.
- D3 2026-11-02: the seeded insights prompts are written from the generic
  recipe of your private experiment (`~/hrono-private/insights`), with no
  name, code or data of that corpus in the repository. Why: that recipe
  measured $2.43 per pass and 8-11 true findings; private evals stay out of
  git. Undo: replace the seeded prompts in the registry.
- D4 2026-11-02: E054 501-505 (grouping, code in since 56c718e, 1086985)
  are not verified in this run. Why: their check needs the bcreg rebuild,
  which runs only on your go. Undo: answer Q3 b.
- D5 2026-11-02: E054 is split into six epics of at most three tickets:
  E055 (511, 512, 521), E056 (506), E057 (531 and the counter), E058 (the
  pass: 532-534), E059 (535, sync) and E060 (536, dashboard); E054 is in
  `archive/`, 501-505 in `backlog/bcreg-rebuild-checks.md`. Why: an epic
  of 18 tickets costs far more per line to build and verify. Undo: none
  needed; the tickets are the same.
- D6 2026-11-02: the per-topic count of unreviewed brief characters is
  derived from stored briefs and pass records, not kept as a stored number.
  Why: a stored counter drifts on hand edits, reverts and undo. Undo:
  amend E057 ticket 2.
- D7 2026-11-02: the dashboard shows insights on the topic page (chip,
  findings card, the existing versions diff), in tree settings and on
  Usage; no Insights page or tab. Why: the goal keeps findings inside the
  brief, and the topic page is where a curator checks a brief. Undo: a new
  epic for a page.
- D8 2026-11-02: "the root always gets a pass" means on a build, or when
  anything under the root is unreviewed; a settle or sync with nothing new
  under the root reviews nothing. Why: a re-pass on an unchanged tree costs
  about $2.50 and finds nothing new. Replaces: the root on every run (E057's
  dry run). Undo: drop the line from E058 ticket 3.
- D9 2026-11-02: the export's root page keeps its opening plus the parts
  the root's insights extension wrote (its findings), not the opening alone.
  Why: an agent reads `root.md` first and the root pass's findings are the
  tree-wide rules the step exists for; today they reach only recall and the
  node page. Replaces: `_routing` keeping only the opening for every root.
  Undo: drop E059 ticket 3. The page's size is measured and logged.
- D10 2026-11-02: the export's extended root page may be up to 5 times the
  unextended one (flask: 4834 vs 1111 bytes, 4.35x), and it keeps every
  line the root pass wrote; no cap on the findings. Why: the findings are
  the tree-wide rules an agent reads root.md for, and 4.8 KB is far below
  the 24 KB root that once made the export cost more than the repository;
  capping would drop findings D9 keeps. Replaces: E059's 2.5x bound.
  Undo: amend E059 ticket 3 with a cap (Conventions and Hazards only, or a
  character budget).
- D11 2026-11-02: with two text models and no `condense` role, a sync
  fails with the build's message instead of placing by the raw vector.
  Why: a sync that silently places on another vector space than the build
  breaks O6, and a paid stage must tell "not configured" from "ambiguous"
  (lessons). Replaces: the sync's "no condense model: placed by the raw
  vector" outcome in that setup. Undo: drop E061 ticket 1's third line.
- D12 2026-11-02: `settle` with insights on runs the due reviews (the
  topics the dry run names, root last) even when churn does not trip, and
  re-briefs only their parents; tree settings get "Review now", which queues
  it, and the estimate line says what runs the reviews. Why: acceptance 1
  found no action that runs the reviews the estimate names (O2 says settle
  does). Replaces: settle doing nothing below its churn trigger. Undo: drop
  E062 ticket 1; a full `maintain` remains the only path.
- D13 2026-11-02: the one-time rewrite after an upgrade (briefs of an
  older default prompt, members moving to condensation vectors) is
  announced on Home and Health with its estimated calls, not suppressed;
  a second unchanged sync must cost nothing. Why: the new prompts and the
  single vector space are what this run delivered (O5, O6); the fault was
  paying 62 calls unwarned. Replaces: nothing. Undo: amend E064 ticket 1.
- D14 2026-11-02: acceptance 1's gaps are fixed in this run as E062-E064
  (about 2.7 h and 450k tokens, then a second acceptance), not proposals: gaps 1-3, 5 and 6 sit in
  O2, O4, O5 and O6, and gaps 4 (source url ignored) and 7 (a flaky test)
  are defects a user hits. Undo: archive E064 ticket 3.
