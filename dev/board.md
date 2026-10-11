# hrono board

Status is the folder each epic sits in. Most-actionable first. Pre-epic
one-ticket history: `done/` (001-221) and `archive/board-pre-epics-2026-10-03.md`.

| id   | title                                                   | status    | priority | depends_on |
|------|---------------------------------------------------------|-----------|----------|------------|
| E050 | the tree carries the architecture — code grouped by what it does, briefs that explain it | backlog | high | - |
| E049 | polish — the Usage README line says what is windowed; one json import | done (580ed26) | low | E047 |
| E044 | the map and the main actions work from the keyboard | done (4fb4cfd) | low | - |
| E047 | polish — the agent-questions card says "last 30 days" and sits in the page | done (ad37949) | medium | E042 |
| E040 | re-asking a past question shows what changed since last time | done (e49e87d) | medium | - |
| E048 | polish — the topic filter never leaves an empty level or a hidden pick | done (8104792) | medium | E046 |
| E046 | a canceled prompt preview says canceled; the topic picker scales | done (f42ea92) | medium | E043 |
| E042 | see how often agents call recall and what they ask | done (53107df) | medium | - |
| E041 | copy a ready snippet to connect an agent to this tree | done (5aafbda) | medium | - |
| E043 | preview an edited prompt on one topic before applying it | done (f9af2bc) | medium | - |
| E045 | polish — source links say which hosts link; no repo-less gitlab link | done (ddbef14) | medium | E039 |
| E039 | the topic page links each section to its file and lists who edited it | done (c3e16fe) | medium | - |
| E038 | polish — the edit_log rebuild is pinned to keep its rows | done (ec714c2) | low | E037 |
| E037 | a stale Undo never undoes a different edit (+E036 test gap, typed write) | done (bb8daf4) | medium | E036 |
| E036 | undo never re-pins a handed-back topic or forgets who wrote the brief | done (7bea1d9) | medium | E034 |
| E034 | undo the last manual edit on a topic (+T3 version-list tidy from E035) | done (bc2ac90) | low | E033 |
| E035 | a brief's previous versions read right and copy back clean | done (1356a4c) | medium | E033 |
| E033 | a brief keeps its previous versions; the page shows what changed | done (bd36a48) | low | - |
| E030 | setup's embed hint reads right; a refused build stays on the page | done (4ff97e8) | low | E026 |
| E032 | the eval README's redaction sentence reads right for stderr | done (0d6efcb) | low | E031 |
| E031 | the eval's probe is injected; README names every redacted output | done (5dad57a) | low | E029 |
| E026 | setup never dead-ends, never builds an unregistered tree (+T3 docstring) | done (4b6b4a7) | medium | E013 |
| E029 | every eval output is redacted, and a test says so | done (5b7be61) | low | E028 |
| E028 | the eval isolation probe catches injected user context    | done (4e5c07b) | low | E027 |
| E023 | the rotation tests say what is true, file readable | done (c3ca086) | low | E021 |
| E027 | index-page section links stop taxing the grep arm         | done (732b19d) | medium | E022 |
| E013 | from an empty install to a built tree, in the panel (+T4 registry copy) | done (4495ae9) | medium | E006 |
| E022 | an export walk settles in two reads; sibling dirs apart | done (6281aaa) | medium | E018 |
| E024 | the activity log can be filtered and paged past the newest 100 | done (15c01d1) | medium | E010 |
| E025 | the missing-syncer test never reaches a real provider | done (39dfd27) | medium | - |
| E010 | the topic page — sections apart, facts before hashes (+T4 one row per section) | done (c305938) | medium | E005 |
| E021 | a secret saved after a key rotation is on the new key | done (fbc291f) | high | E012 |
| E009 | fix what health shows, from the health page | done (421a0df) | medium | E007 |
| E008 | the panel shows what was spent; Home runs in SQL; stage count | done (cf801a6) | medium | E002, E005 |
| E011 | find things — search, outline, file to topic            | done (ec0bcfb) | medium | E005 |
| E007 | one vocabulary, and a Guide that tells the truth (+running not partial) | done (3cf756b) | medium | E005 |
| E018 | an export an agent routes by and cites; cheaper than raw | done (684b78d) | high | E004 |
| E012 | manage users in the panel                               | done (a3ba650) | medium | E005      |
| E019 | the echo gate spares a real brief about the prompt's words | done (a2b505d) | medium | E015 |
| E020 | a git source URL can never reach git as an option       | done (39e15c3) | medium | -     |
| E016 | a claude-code text model can be registered              | done (7a3df4e) | high | - |
| E005 | the shell and home — no overflow, "is it up to date"    | done (ebad3d8) | high | -       |
| E014 | the map at scale — readable on 100+ topics; graph flake | done (c0a47bf) | medium | -        |
| E017 | a test suite that runs in under a minute                | done      | highest  | -          |
| E006 | Settings — one collection at a time, fillable forms     | done (026d8ea) | high | -          |
| E015 | every talk-back caught (condensations, briefs), bounded | done (3ece8be) | high | E001      |
| E004 | prove the export — a real agent answers from the folder | done (b4332a8) | high | -          |
| E002 | a failed run never claims it did nothing                | done (16fb12c) | high | -          |
| E003 | a real build does not fail at random; slow write says so| done      | high     | -          |
| E001 | the condensation gate holds on a corpus of any size     | done      | high     | -          |

Backlog and todo empty. E049 merged; every REQUIREMENTS line is [have] or [skip]. Board satisfied.

## Rejected (deferred — each has a pull-in trigger in archive/)
- E043-followups: Co-Authored-By trailer on 45da64f — commit hygiene for the merge step, not product work.
- 043 service tier — no route holds business rules of its own yet.
- 046 OS-keychain token — until hrono ships to end-user workstations.
- 050 job priorities — one worker, no measured queue wait.
- 077 ANN recall index — only if recall is still slow after #194 (~500k passages).
- no-clusters-on-sixteen-random-vectors — covered by E003 T1 (all-noise is one topic, tested on structureless vectors).
- hop-limit-3-vs-4-needs-a-deeper-corpus — own repo builds 3 levels; pull in when a ~4-level corpus (whole repo incl. tests via API key) is built for E018-style measurement.
- suite-has-no-xdist (backlog, po E006 review) — duplicate of E017 T1, in flight.
- test-manual-split-dense-topic-flake (backlog, qa E017 r1) — one unreproduced red in 34+ runs; pull in if it recurs, keeping the full failure text.
- commit-split-after-qa-has-seen (backlog, dev E009) — not a rule change: a multi-ticket commit qa has already seen is waived at PO review (E009, E008).
- brief-cost-needs-a-ledger-link (backlog, qa E010) — per-run/model/user cost is shown (E008); a per-brief price needs a migration no requirement asks for. Pull in if a curator needs spend per topic.
- E031-followups process notes (backlog, qa E031) — log the handed-over head; one commit per ticket: dev conventions already, not work.
- E030-followups (backlog, qa E030 r1) — the refusal is reachable only by a hand-crafted post or a tree deleted mid-setup; nowrap-test and commit-wording lines are taste. Polish converges here; pull in if a user reports it. Re-raised at po review cd31189: same finding, same call.
- E033-followups (qa r1 + po): `.diff-*` CSS rules sit inside the chip block — taste. The rest is E035.
- E035-followups (qa r1): README line wrap is taste; one-commit-per-ticket is a dev convention already. The code lines are E034 T3.
- E034-followups: the T1+T2 one-commit line is process (waived at review); the rest is E036.
- E036-followups: the one-commit-per-ticket line is process (dev convention already); the rest is E037.
- E037-followups: README:118-120 reflow is taste; one-commit-per-ticket is a dev convention already. The migration test is E038.
- E039-followups commit-wording lines (31b5f83, c3e16fe bodies) — merged on main; main history is not rewritten.
- E046-followups: 461+462 in one commit — process note, no code to change; dev convention already.
- E047-followups: 471-473 in one commit — process note; one commit per ticket is a dev convention already.
