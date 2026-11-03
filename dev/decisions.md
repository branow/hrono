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
- D15 2026-11-02: E062's followups are fixed in this run, not left for
  later: a `hrono tree review <tree>` CLI command (the README pointed a CLI
  admin at `POST /jobs`, documented as debugging only), the README cost
  ($2.80 a topic, as the dry run says), the Runs message after Review now,
  the two-source evidence version, and the nav overlaps at 390, all in E063;
  the manual-split flake in E064. Why: each is a gap a new user hits on O2
  or the 390 bar. Replaces: nothing. Undo: drop E063 ticket 3.
- D16 2026-11-03: E064 goes back for one round instead of merging with
  followups: a tree synced before the upgrade keeps its raw-vector monitor
  baseline, so its second unchanged sync can still settle and pay calls,
  the very fault E064 fixes. The round also fixes the boot torch race in
  the app (a sync right after `hrono serve` fails "the reduction failed")
  rather than in the test, and steadies the live-run browser flake.
  Why: the bench copy had no baseline, so qa could not see it; most real
  upgraded trees have one. Replaces: merging at 317990a. Undo: accept
  317990a and leave the items in backlog/E064-followups.md.
- D17 2026-11-03: E063 accepted at eb7e939; its followups become E065
  instead of waiting for acceptance 2: a review that fails from Review now
  or `hrono tree review` never shows on its topic (O4 holds only for a
  sync), the failed card also says "found nothing to add", the uk chip shows
  English level words, the low chip looks like plain text, E063's hidden
  closed disclosures break find-in-page; plus `POST /jobs` settle on an
  unknown tree and an unbounded threshold. Why: the first is a gap on an
  asked outcome a curator hits on a provider outage. Replaces: leaving them
  in backlog. Undo: archive E065, items back to backlog/E063-followups.md.
- D18 2026-11-03: E065 accepted at d347ea1; its four small followups
  (the CLI failure line naming the topic, the Review now run title,
  POST /jobs other ops on an unknown tree, ui-check reading undrawn closed
  disclosures) wait for acceptance 2 instead of a new epic. Why: none stops
  O2 or O4, an epic of polish alone costs about 120k of the 376k left, and
  acceptance 2 needs 150k. Replaces: nothing. Undo: author an epic from
  backlog/E065-followups.md.
- D19 2026-11-03: acceptance 2 passed O1-O6 with six small gaps; they are
  one epic, E066 (findings chip and code, the settings line after reviews,
  the review run title, the upgrade estimate with cache writes and to
  cents, two fast-suite flakes), with the CLI failure line naming the topic
  from E065's followups, then a scoped acceptance 3. Why: each is a gap a
  curator sees on O4 or a contributor's red gate; the estimate off by 2x
  misleads an admin deciding to upgrade. Budget: about 120k + 150k of the
  320k left. Replaces: ending the run on acceptance 2. Undo: archive E066,
  items back to backlog.
- D20 2026-11-03: E066 accepted; its four qa followups (odd backtick count
  shows raw, uk failure line keeps English item, run Spent card to four
  decimals, an idle settle titled as placing) wait for acceptance 3 instead
  of a new epic. Why: none stops an outcome, and an epic (~120k) plus
  acceptance 3 (~150k) exceeds the 232k left. Replaces: nothing. Undo:
  author an epic from backlog/E066-followups.md.
