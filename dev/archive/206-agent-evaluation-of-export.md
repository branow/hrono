---
id: 206
title: prove the export — a real agent answers real questions from the folder
priority: high
size: big
depends_on: [204, 217]
spec_refs: [REQUIREMENTS.md#10 (86), .e2e/]
---

## Context
The whole product is the claim that an agent finds things in this folder faster than in the raw repo. Nothing has ever tested that with an agent. Compaction (#204) changes the shape agents navigate, so it needs a measurement, not an opinion.

## Description
A repeatable evaluation, run by hand (it costs money), living under `.e2e/`.

Given an exported folder and a question set with known answers (the file or identifier that settles each question), run a real agent (Claude Code, headless) with read access to the export only. Record per question: pages opened in order, hops from root to the answer, tokens, time, and whether the answer cites the right source.

Compare at least: hop limits 2, 3 and 4 on the same tree; and the export against the raw repository as a baseline.

Write the results as a report the user can read: a table, and the questions that failed with the path the agent took. Author the question set for one real corpus (hrono's own repository is the obvious one), including questions whose answer is deep and questions with no answer.

The agent must run in a directory that carries no project or user memory — the review found the user-level CLAUDE.md leaking into model calls (#217).

## Acceptance criteria
- [ ] one command runs the evaluation over an export and writes a report
- [ ] at least 15 questions with known answers for one real corpus, including no-answer controls
- [ ] the report gives hops, pages read, tokens and correctness per question, and totals per hop limit
- [ ] a baseline against the raw repo is in the same report
- [ ] the run is isolated from the operator's Claude memory, and the report says how that was verified
- [ ] findings that mean the export shape is wrong are filed as backlog tickets, not fixed here

## Out of scope
CI integration. Tuning the compaction constants (a follow-up from the findings).

## Review log
- 2026-10-03 po: authored from the requirements review and the UI review of the same day, at the user's request.
- 2026-10-03 po: now depends on #217 — evaluating an agent over an export whose pages are model refusals measures nothing.
