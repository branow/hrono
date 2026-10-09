---
id: E004
title: prove the export — a real agent answers real questions from the folder
priority: high
depends_on: []
requirements: [86]
---

## Goal
The product's claim is that an agent finds things in the export faster than in
the raw repo. Measure it, by hand-run evaluation under `.e2e/` (it costs money).

## Tickets

### 1 the question set and the runner
Change: ≥ 15 questions with known answers (settling file/identifier) for
hrono's own repo, incl. deep and no-answer ones; one command runs headless
Claude Code over an export with read access to it only, in a directory with no
project or user memory.
Done when:
- [ ] one command runs the set over an export and writes a report
- [ ] isolation from operator memory is verified and the report says how
Look at: .e2e/, archive/206

### 2 the comparison and the report
Change: run hop limits 2, 3, 4 and the raw repo as baseline.
Done when:
- [ ] per question: pages opened in order, hops, tokens, time, correct source
- [ ] totals per hop limit and baseline in one table; failed paths listed
- [ ] shape findings filed to backlog/, not fixed here

## Out of scope
- changing the export shape

## Log
- 2026-10-03 po: created from #206.
- 2026-10-03 dev: round 1 started on epic/E004; building hrono's own tree (src + top docs, 268 sections) on a scratch claude-code server for the measurement.
- T1 06b8075: runner + 22 questions (19 answerable, 3 no-answer); 26 tests in tests/eval; drove it for real (raw arm, q01+q20, haiku: 2/2, isolation verified: control quoted canary + operator word, isolated quoted neither). Mutations: none-grade cite check, page header check, path match, outside-copy page, depth, settler match (survived, fixture too symmetric -> added b.py test, now bites), URI strip, error subtype.
- T2 3aa8199: hop limits 2/3/4 + raw in one report, pages in order per question, cited export page graded by its header, twins named, --rerender, --tools. Ran for real: 88 sessions (grep) + 66 (walk-only), isolation verified both; evidence/E004/README.md. Mutations: twins len>1 (survived, fixture had only twins -> added a distinct arm, bites), cited-page resolve, /corpus/ strip, fingerprint bytes, short path.
- Findings filed to backlog/ (4): export-costs-more-than-the-raw-repo, briefs-state-facts-without-their-file, topic-directories-are-named-by-a-framing-phrase, hop-limit-3-vs-4-needs-a-deeper-corpus. Question fixes from the run: q10 accepts "median" (_majority takes the median), q12/q13 accept GLOSSARY.md.
- 2026-10-03 qa: round 1 FAIL at 3aa8199. Gate green (1720 passed, 4 skipped); drove a live haiku run (q01,q20 x raw+levels-2, isolation verified, 2/2 each) and --rerender of dev's grep run (matches evidence). Findings: isolation verdict untested (mutations verified=not leaked and leaked=False survive), one timed-out/garbled session discards the whole paid run (runs.jsonl only written at the end), user-memory leg of the probe hardcodes this operator's own marker word, --rerender with a subset of --only/--arm crashes. See qa verdict.
- 2026-10-03 dev: round 2 ad979f7: isolation_verdict pure + probe injectable (6 verdict cases, both qa mutations now killed), --operator-mark replaces a hardcoded operator word (report says when user memory untested; evidence isolation.json backfilled with the mark actually used and re-rendered, totals unchanged), timeout/garbled line -> error Run and runs.jsonl appended per session, --rerender filters to requested arms/questions and names unrecorded pairs. 43 tests in tests/eval; mutations killed: verdict x3, timeout, malformed, write-at-end, no select, no missing check, untested note.
- 2026-10-03 po: restarted — orphaned by a stopped run; resumes on its branch and worktree.
- 2026-10-03 qa: round 2 PASS at ad979f7. Lint clean, tests/eval 43 passed (0.55s). Round-1 findings re-checked: isolation_verdict tested, --operator-mark replaces the hardcoded word, runs.jsonl appended per session with timeout/garbled as error Runs, --rerender subset filters and names unrecorded pairs (drove full + q01,q20 + bogus arm on dev's 2026-10-03 run: totals match evidence). Drove live haiku q01,q20 x raw+levels-2 with --operator-mark <word>: isolation verified, 4/4, runs.jsonl 4 lines. Mutations killed: dev's verdict control-check, mine: malformed-not-failure, case-sensitive _quotes, no per-session write, select_runs keep-all. Notes (non-blocking): --only silently drops unknown ids; a non-timeout exception in one session still discards sessions finishing after it; new tests monkeypatch subprocess.run where check_isolation took DI.
- 2026-10-03 po: ACCEPT at ad979f7. Both tickets' Done-when met by qa's drive and evidence/E004 (22 q, 4 arms + walk run, isolation verified, failed paths listed, 4 findings filed); README + .e2e/eval/README document it. Req 86 -> [have] on merge. qa's non-blocking notes -> backlog/export-eval-runner-rough-edges.
- merged to main at b4332a8
