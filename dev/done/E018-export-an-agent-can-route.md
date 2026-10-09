---
id: E018
title: an export an agent routes by and cites — and that costs less than the raw repo
priority: high
depends_on: [E004]
requirements: [86]
---

## Goal
E004 measured the export losing to the raw checkout on hrono's own repo: more
tokens, same or fewer answers, agents unable to cite. Fix what the agent sees
first (directory names, root page, citations), then re-measure with E004's runner.

## Tickets

### 1 topic directories are named by their subject
Change: `_directory` slugs the topic's name (#212), not the brief's first
sentence; no "these-condensations-describe-..." prefixes.
Done when:
- [ ] on hrono's own export no directory starts with a framing phrase; ls in evidence/E018/
Look at: src/hrono/export/render.py `_directory`, #212 naming

### 2 a brief's constants link to the section that settles them
Change: a concrete fact in a brief (constant, env var, size) carries a link to
the member section page it came from; members are already known at render.
Done when:
- [ ] walk-only rerun: no right answer cites only root.md or a brief.md for a
  fact a section states
Look at: summarize/brief.py, brief_upper.py prompts; export/render.py

### 3 re-measure against the raw checkout
Change: rerun `.e2e/eval/run.py` (grep and walk-only, 2/3 hops + raw). If root.md
still dominates cost, shrink it to a routing page.
Done when:
- [ ] report in evidence/E018/ with before (E004) / after tokens, correct, reads
- [ ] export tokens <= raw, or the Log states why not and what would change it

### 4 the eval runner's two rough edges
Change: `--only` stops and names unknown question ids (as `--rerender` does);
a non-timeout exception in one session becomes an error Run, never discarding
sessions that finish after it.
Done when:
- [ ] both covered by tests in tests/eval, each mutation-checked
Look at: .e2e/eval/run.py

## Out of scope
- hop limit 3 vs 4 on a deeper corpus (needs a ~4-level tree; rejected for now)
- docs/Confluence corpora measurement

## Log
- 2026-10-03 po: created from E004 backlog: topic-directories-are-named-by-a-framing-phrase, briefs-state-facts-without-their-file, export-costs-more-than-the-raw-repo.
- 2026-10-03 po: folded backlog export-eval-runner-rough-edges (E004 qa notes) as ticket 4.
- 2026-10-03 po: started (E015 merged, brief.py overlap gone).
- 2026-10-03 dev: round 1 started, worktree .claude/worktrees/E018
- T1+T2 4e71010 (one commit: both change export/render.py): naming.unframe strips the announcing clause ("These condensations describe...", "What this is: a set of notes on...") so a directory is named by its subject; export/citations.py links a brief's backticked spans, UPPER_SNAKE names, decimals and numbers to the (<=3) section pages in its subtree that contain them, relative to the page. Tests: tests/test_unframe.py, tests/export/test_citations.py, 3 render tests. Mutations killed: _MOST, _PER_LINE, lookbehind, relpath, subtree scope, summary unframe, unframe guards x3.
- T4 d61dd25: --only names unknown ids and stops before writing; a session that raises becomes an error Run ("RuntimeError: boom") and the later sessions still land. Mutations killed: except type, future->task mapping, unknown guard x2, error text.
- T3 in progress: hrono's own tree (snapshot of f3e4853, src + top docs) building on a scratch claude-code server (.claude/worktrees/E018/.scratch, port 18740); text models inserted into the registry directly (claude-code registration defect, E016).
- 2026-10-03 dev: BLOCKED on T3: claude-code returns 'You've hit your session limit, resets 4:30pm Europe/Kiev' (maintain job failed with 429 before any condense). T1, T2, T4 committed (4e71010, d61dd25). Resume: rerun .scratch server (port 18740, key/token in .claude/worktrees/E018/.scratch; models inserted directly into registry) with 'hrono tree maintain default', then export levels 2/3 + raw and run .e2e/eval/run.py grep and walk.
- 2026-10-03 po: ruling: resume T3 after the 16:30 Europe/Kiev reset, same round; do not split it. T1/T2 Done-when need the same real export, and T3 is the epic's outcome (req 86). If the limit hits again mid-run, stop blocked again with what finished.
- 2026-10-03 dev: round 2, T3 done after the 16:30 reset. Maintain job succeeded (269 condenses, 21 briefs; no limit hit again). Evidence in evidence/E018/ (README.md has the before/after table; directories.txt is hrono's own export listing).
- Real export showed T1 incomplete: "Overview:"-labelled and "a set of condensed module notes for" briefs still named directories "overview-these-condensations-..." / "set-of-condensed-...". Fixed in 1fdb609 (naming.unframe; 3 new cases, 2 mutations killed). After it no directory starts with a framing phrase (directories.txt). Left as is: two siblings both named "hrono-is-a-hierarchical-incrementally-updated-knowledge-base" (disambiguated by -5/-15, but not telling), and level-1 "hrono-parent-brief-20".
- T2 walk-only: 0 of 44 export-arm answers cite only root.md/brief.md (before and after).
- T3 finding: the first re-measure (1fdb609) cost MORE than E004 (grep levels-2 849k vs 620k): the T2 citation links (full path twice per citation) were 60% of root.md's bytes (24.5 KB). d28484f: an index page (any node with children) keeps its opening plus Children list, and a citation is `[§](path)`. Root 24.5 KB -> 4.6 KB (levels-2), 29.6 -> 1.0 KB (levels-3).
- T3 result (22 questions): grep levels-2 434k, levels-3 382k vs raw 320k (E004: 620k/539k vs 341k); walk levels-2 1,088k, levels-3 758k vs raw 509k (E004: 857k/765k vs 415k). Correct: grep 21/20/22, walk 19/20/21 of 22. NOT <= raw. Why: the hrono tree is 1.6 MB / 268 files, the agent greps or opens the right file in 1-2 reads (raw 0.5 reads, walk 1.5), while an export costs 1-2 index hops on top (walk 4.1-4.2 reads); the gap in grep is ~60-110k tokens over 22 questions, near the run-to-run noise of raw (300-340k). What would change it: a corpus where raw cannot be grepped in one step (Confluence/Notion, or a repo 10x larger), where the hop count pays for itself; or index entries that name the file to open so a walk takes 2 reads. Neither is in this epic.
- Finished: maintain; exports levels-2, levels-3 (run2) and raw; eval grep and walk x levels-2/levels-3/raw twice (before and after routing). Nothing to redo. T4 done in round 1. Server on port 18740 left running for qa to re-export.
- 2026-10-03 qa: round 2 FAIL at d856da4: re-exported the dev's db from the qa worktree (byte-identical l2/l3, 0 dangling [§] of 925), lint+380 tests clean; findings: citations make export 6-9 s on 268 sections (CLI 10 s timeout hit, panel re-renders per click), mutations survive (routing root-only, heading lstrip, _routing prose), unframe strips bare leading prepositions, levels-3 dir 'hrono-parent-brief', T1+T2 one commit. Re-ran dev's lookbehind mutation (killed).
- 2026-10-03 dev: round 3, 12528c8 (one fix commit; earlier commits are qa-seen and not rewritten, so the one-commit-per-ticket split of T1/T2/T3 cannot be restored). Finding 1: FactIndex splits each section into words once, a one-word fact is a dict lookup, only the kept routing text is cited; produce() on the 268-file corpus 6.1/8.5 s -> 0.53 s at levels 2 and 3, timing test (300 sections, 3000 lines, 0.2 s). Finding 2: tests for index-vs-leaf trimming, heading with lstrip, two headings before prose; all three mutations killed. Finding 3: filler/preposition stripped only after an announcement and only after a filler noun (negatives added). Finding 4: unframe drops a trailing '— parent brief/overview' label; levels-3 dir is now hrono-20. Finding 5: acknowledged, not fixable without rewriting seen history; qa-seen fix commits stay.
- 2026-10-03 qa: round 3 FAIL at 12528c8: round-2 findings 1-4 fixed (CLI export of the dev db from the qa worktree on 18741 takes 1.2 s; produce() 0.53 s; l2/l3 identical to run2 apart from the two renamed dirs; 925/929 [§] links, 0 dangling; lint clean, 619 affected tests pass; the three round-2 mutations and dev's announcement guard are killed). Still failing: the new FactIndex code has surviving mutants (dot-head words dropped, lookbehind and lookahead removed in the regex fallback), and the commit split per ticket (finding 5) is unchanged.
- 2026-10-03 po: stuck after 3 rounds (FactIndex mutants: dot-head words, regex-fallback lookbehind/lookahead; one commit per ticket). needs-user: rule the history stands (rec: yes, as for E011; per-ticket commits from round 1 on) and grant one dev round for the 3 mutants only?
- 2026-10-03 po: user ruled yes — history stands (per-ticket commits from here on); one dev round for the 3 FactIndex mutants only (dot-head words, regex-fallback lookbehind, lookahead). Restarting.
- 2026-10-03 dev: round 1 (after ruling), e6ce35e: two tests for the 3 FactIndex mutants (dot-head words; fallback lookbehind and lookahead on '64 KB'). All 3 mutations now fail a test; ruff clean, tests/export/test_citations.py 17 pass. No source change.
- 2026-10-03 qa: round 1 (after ruling) PASS at e6ce35e: the head differs from 12528c8 (round 3, export driven: CLI 1.2 s, 0 dangling [§]) only by 19 test lines, so the round-3 drive stands; ruff clean, 245 affected tests pass, new tests 0.07 s. Re-ran dev's 3 FactIndex mutants (dot-head words, fallback lookbehind, lookahead) and 4 of my own (lookbehind without the dot, dot-head only past index 2, _RUN as \w+, KB dropped from the unit list): all killed. History stands per the user's ruling.
- 2026-10-03 po: review ACCEPT at e6ce35e: T1 dirs named by subject (directories.txt), T2 0/44 walk answers cite only root/brief, T3 cost down 30-50% vs E004 but not <= raw, Log states why and what would change it (allowed by Done-when), T4 tested; README documents [§] and index pages. Follow-up: backlog/export-index-entries-name-the-file.md.
- merged to main at 684b78d
