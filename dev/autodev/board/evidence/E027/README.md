# E027 evidence: the root carries no section links

Tree: hrono at 6281aaa, `filter.only` src/** + README, CONTRIBUTING, GLOSSARY,
pyproject (303 sections), REBUILT for this epic through claude-code (haiku
condense/judge, sonnet briefs). This build stored three levels (root, 2, 21),
so the arm is `--levels 2` (root + 21 topics; root.md lists 21 entries), the
nearest shape to E022's. It is NOT E022's tree, so E022's numbers are not the
baseline; `head` (main, 1 link per entry because the page is at full WIDTH) and
`noroot` are exported and measured the same way here. Agent sonnet, 22 questions.

| run | arm | correct | reads | tokens | $ | root.md |
|---|---|---|---|---|---|---|
| walk | head | 18/22 | 3.2 | 871,310 | 1.45 | 8,174 B |
| walk | head, second run | 17/22 | 3.3 | 921,701 | 1.51 | |
| walk | noroot (shipped) | 19/22 | 3.5 | 832,892 | 1.43 | 5,465 B |
| walk | noroot, second run | 18/22 | 3.7 | 961,432 | 1.57 | |
| grep | head | 21/22 | 1.3 | 534,872 | 0.80 | 8,174 B |
| grep | head, second run | 21/22 | 1.2 | 480,106 | 0.74 | |
| grep | noroot (shipped) | 20/22 | 1.1 | 429,444 | 0.67 | 5,465 B |
| grep | noroot, second run | 20/22 | 1.3 | 430,045 | 0.66 | |

Verdict (round 2, two runs per arm per variant). Root.md 5,465 B (<= 6 KB).
Grep: noroot 429k/430k against head 535k/480k, below head on every run (-20%,
-10%). Walk: head 871k/922k (mean 896k), noroot 833k/961k (mean 897k). Under
head in run 1, 4% over in run 2, a tie on the mean; head alone moves 50k
between its two runs, so the walk difference is inside run variance. Said
plainly: the walk bar "<= head" holds on one run of two and on the mean only as
a tie. Correctness against head: grep 20/22 and 20/22 against 21/22 and 21/22
(one question), walk 19/22 and 18/22 against 18/22 and 17/22 (noroot ahead).
No arm is worse by more than one question.

Grep settler-reached 9/19 -> 4/19 is noise. The same arm and tree, rerun,
gives noroot 4/19 then 9/19, head 9/19 then 7/19: one arm swings five
questions between identical runs. The metric counts a session as reaching the
settler only if it Read a section page; a grep agent often answers from the
Grep output alone (head q02 and q05 never read a page, in both runs), so it
tracks how often the model chose to open a page, not whether the tree led it
there. Source-right, which needs the settling file cited, is 21/22 for noroot
in both runs and 21/22 for head. Noroot does not hide the settler from grep.

Variant (a), path-only entries, was rendered and NOT shipped: the relative path
carries the topic's directory slug (about 60 characters), which is longer than
the `[last two path parts]` text it would replace, so the links grew the page
(9,555 B against 8,174 B) rather than shrinking it.

On this tree no page below the root is exported at --levels 2, so the links
below the root are not measured here; they are unchanged.
