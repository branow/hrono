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
