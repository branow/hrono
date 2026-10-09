# hop limits 3 and 4 cannot be compared on hrono's own repo

What: hrono's own repo (src + top docs, 268 sections) builds to 3 stored
levels, so `--levels 3` and `--levels 4` export byte-identical folders and
E004's levels-3/levels-4 difference (21/22 vs 20/22) is agent variance only.
The report says so (it fingerprints the folders).

Why it matters: #204's depth-for-width trade is only exercised on a tree with
more stored levels than the hop limit. Measuring it needs a corpus of a few
thousand sections, or the whole repo including tests (852 sections in the demo
home) built through an API-key connection.

Evidence: .autodev/board/evidence/E004/grep/report.md, Totals.
