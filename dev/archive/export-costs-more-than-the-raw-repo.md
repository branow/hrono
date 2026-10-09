# on hrono's own repo the export costs an agent more than the raw checkout, for no gain

What: E004 measured headless Claude Code (sonnet) answering 22 known-answer
questions over hrono's own repo (268 sections, tree built 2026-10-03 from
f3e4853). With Read/Glob/Grep:

| arm | correct | tokens | cost $ |
|---|---|---|---|
| export, 2 hops | 21/22 | 619,880 | 1.06 |
| export, 3 hops | 21/22 | 538,647 | 0.97 |
| raw checkout | 21/22 | 340,982 | 0.42 |

With Read/Glob only (nothing to do but walk): export 2 hops 17/22, 3 hops
15/22, raw 21/22 at half the tokens; raw reached the settling file in 19/19
answerable questions at 1.4 reads, the export in 12-13/19 at 2.1-3.2 reads.

Why: with grep, agents read root.md (14-18 KB) and then grep the folder rather
than walk it, so every session pays for root.md plus grep hits duplicated
across briefs and sections. Without grep, a code repo's own file names already
route (`Glob *fusion*`), and the export's topic directories do not
(see topic-directories-are-named-by-a-framing-phrase.md).

Where it matters: the product claim (REQUIREMENTS #86) is that an agent finds
things faster in the export. On this corpus it does not. A corpus whose file
names do not route (docs, Confluence, Notion) may answer differently and has
not been measured.

Evidence: .autodev/board/evidence/E004/{grep,walk}/report.md; rerun with
.e2e/eval/run.py.
