---
id: E058
title: a pass reviews a large subtree with the lookups and extends its brief in place
priority: high
kinds: [backend]
depends_on: [E057]
outcomes: [O1, O2, O3]
journeys: [J3, J8, J9]
waits_on: []
---

## Goal
With insights on, an agent reading the tree should find in the area brief
the rules no single section states, the siblings that differ, and the wrong
statements of the cheaper brief corrected, with evidence. This epic runs the
pass: one read-only review per selected topic on the existing lookups with
a turn cap, then one extend call that rewrites the brief in place; the
cheaper brief stays as the previous version, a pinned brief is never
overwritten, and the parent is clustered and briefed from the extended
brief. Runs inside build-tree and `settle`. Moves O1 (off = same tree),
O2, O3 (pin, export) (E054 532-534).

## Build on
- The measured recipe, step by step: `dev/research/insights-recipe.md`
  ("What to take" 1-10): the v7 review frame (brief and one-line index up
  front, six fixed grep questions first, narrow reads, source confirms,
  at most 15 findings with the record fields of item 6, checked-and-dropped
  list), and the extend prompt of item 7. Seed both as editable prompts
  (two prompts, both run on the `insights` model; how the prompt registry
  tells them apart is dev's call), generic, no private names (D3).
- Lookups: `summarize/lookup.py` `files()` and `toolbox()`; add the
  subtree's briefs as `brief/<path>.md` files, scope the files to the
  topic's descendants, and give `toolbox` a `most` argument (about 60 for
  a pass; the three provider loops already iterate `toolbox.turns`).
- Briefs and history: `briefs.upsert` writes `brief_versions` (E033); add a
  reason for an insights extend whose provenance names the model and the
  pass. Pins: `pins.is_pinned`, checked before the extend write, not before
  the review.
- Where it runs: the level loop in `summarize/build_tree.py` after
  `brief_upper` of a level; a `settle` stage in `tree/settle.py`. Usage:
  calls go through the ledger with role `insights` like every other call.
- Rejected: a separate insights file or section (decided 2026-11-02);
  three prompts per angle ($11 a pass); whole-file reads ($3.96 a pass).

## Tickets

### 1 the review runs read-only on the lookups and stores its findings
Done when:
- [ ] on the flask copy (threshold lowered, insights model = claude-code
      Opus), one review of a selected topic runs within the turn cap, uses
      only the read-only lookups, and stores each finding with statement,
      evidence (file, lines, version), confidence, placement (where the
      brief stated it or should) and the dropped hypotheses; the rows are
      in `evidence/E058/` (real calls on the flask copy: at most 10, D2)
- [ ] a review that hits the turn cap or a provider error stores nothing
      half-done and the run's log says why
- [ ] the review's lookups cannot read a file outside the topic's subtree
- [ ] with no model holding the `insights` role, no pass runs (no fallback
      to the sole text model, `summarize/resolve.py:55`); the job and the
      dry run say why in plain words

### 2 the extend call rewrites the brief in place, keeping the cheaper one
Done when:
- [ ] after the pass, the topic's brief is the extended text, its previous
      version is the cheaper brief with provenance naming the insights model
      and the pass (`GET` the node's versions shows both)
- [ ] a pinned topic keeps its brief byte for byte; its findings are stored
      and marked not applied
- [ ] `hrono tree export` of the flask copy renders the extended brief;
      `grep -ri insight` over the export is empty

### 3 build-tree and settle run the passes the counter selects
Done when:
- [ ] `settle` on the flask copy with the step on gives one pass to each
      topic whose count reaches the threshold, and to the root, and to no
      other; the job's stages count reviews, extends and findings; the
      parent of a reviewed topic is briefed from the extended brief
      (its brief input hash shows it)
- [ ] the root gets a pass when it never had one or has unreviewed
      characters; a second `settle` with nothing changed runs no pass, and
      the dry run says the same (D8)
- [ ] with the step off, a build makes no insights call (zero `insights`
      ledger rows) and writes the same tree as before this epic (a test
      compares the two)

## Out of scope
- Re-passes on sync (E059); dashboard (E060).

## Tried

## Log
- 2026-11-02 po: created from E054 532-534 and the insights-recipe
  research (O1-O3).
- 2026-11-02 po: folded E057 qa followups (no insights model means no
  pass; root re-pass only when something under it changed, D8).
- 2026-11-02 dev r1: T1-T3 on epic/E058 (branch merged epic/E057 first: not yet on main). Real flask copy, claude-code Opus, 6 real calls: settle (forced drift) gave a root pass, 10 findings, brief 7822 to 11920 chars; settle also re-clustered the copy's leaves (21 not 16), so build-tree at threshold 50000 gave passes to topic 17 (5 findings) and the root (6), not 18 (39514 below); parent re-briefed from the extended brief; 2nd build-tree 0 reviews; export carries the extended brief, grep -ri insight empty; versions page shows "replaced by an insights review (opus)" after restart; no model: job result note, 0 calls. Rows in dev/evidence/E058/. Mutations run (tests fail): lookups scope removed, pin checks removed, sync guard removed, first-version protection removed. Extended brief keeps the cheaper brief's provenance so brief-upper leaves it fresh. sync_chain passes reviewing=False (E059).
- 2026-11-02 qa r1: pass at b322174. Drove on the flask copy (dev's db after its 6 real calls, no new real calls): node 17 and root versions read "replaced by an insights review (opus)" after a restart; export grep -ri insight empty with 17's extension present; build-tree job with no insights model: note, 0 calls; dry run at 30000/50000/huge and hostile thresholds (0, -5, text: refused). Found and fixed: a lower pass re-briefed an already reviewed root and dropped its extension without a new pass (dry run said 1 pass, now 18 + root, 4ff1226; docs 641b7be); a brace in prose around a review's JSON lost a paid review (b322174). Re-ran mutations: lookups scope removed and pin checks removed (each fails a test); sync_chain reviewing=False removed stays green (followup). Full suite 2299 passed. Followups: dev/backlog/E058-followups.md.
- 2026-11-02 po: accepted at b322174. The flask passes hold real, sourced findings (topic 17: the session lifetime cuts non-permanent sessions; the root: 10, the dotenv rules misstated in the cheaper notes); pin, export and off-is-same are tested. Followups folded: the sync guard test and the root page into E059 (D9), the topic's date into E060.
