# E022 evidence: an export walk in two reads

**Superseded numbers.** The rows marked `after-2` below were measured on an
earlier renderer (3 section links per entry, root.md 11,474 B), which no
longer exists. The shipped renderer (head of epic/E022: 2 links per entry,
page held within one SECTION) gives root.md 9,507 B on this same tree; its
measurement is the `head` rows and `head/`. Nothing else in the exported tree
differs (287 files, only root.md changed).

Tree: hrono at f3e4853, `filter.only` src/** + README, CONTRIBUTING, GLOSSARY,
pyproject (268 sections), REBUILT for this epic (the E018 database was
deleted with its worktree) through claude-code, haiku condense, sonnet briefs.
It came out with 18 topics and a root, two stored levels, so levels-2 and
levels-3 export the same folder and only levels-2 is run. The clustering is not
E018's, so E018's numbers are not the comparison; the same tree is exported
twice instead, with the renderer at main (684b78d, `before-2`) and at this
branch (`after-2`), and measured the same way. Agent sonnet, 22 questions.

| run | arm | correct | reads | reads to settler | tokens | $ |
|---|---|---|---|---|---|---|
| walk | before-2 | 19/22 | 3.7 | 3.9 | 1,007,079 | 1.63 |
| walk | after-2 (3 section links) | 18/22 | 3.0 | 2.9 | 799,178 | 1.42 |
| walk | after-2, second run (links ranked by the brief's facts) | 20/22 | 3.1 | 3.0 | 854,292 | 1.49 |
| walk | after, 6 links (not kept) | 19/22 | 2.9 | 2.7 | 932,470 | 1.64 |
| walk | **head (2 links, shipped)** | 19/22 | 3.1 | 3.2 | 827,013 | 1.46 |
| walk | raw | 22/22 | 1.5 | 1.3 | 410,154 | 0.73 |
| grep | before-2 | 21/22 | 1.2 | 2.0 | 373,817 | 0.60 |
| grep | after-2 | 21/22 | 1.3 | 1.9 | 544,303 | 0.88 |
| grep | after-2, second run | 21/22 | 1.3 | 1.9 | 554,006 | 0.89 |
| grep | **head (2 links, shipped)** | 21/22 | 1.2 | 1.7 | 463,568 | 0.77 |
| grep | raw | 22/22 | 0.6 | 1.0 | 379,670 | 0.46 |

Page sizes: root.md 5,040 bytes before, 11,474 with 3 links per entry (superseded),
9,507 at the head (2 links per entry), 17,369 with 6 links.

Verdict at the head: walk is NOT at or under raw (827k vs 410k tokens, 3.1
reads vs 1.5), but it is 18% under before-2 (1,007k) and the grep arm, which
the 11.5 KB root had pushed to 544k, is back to 464k (before 374k, raw 380k).
The smaller root lowered grep as predicted; walk did not move (799k and 854k
at 11.5 KB, 827k at 9.5 KB: run variance), so the 'smaller root lowers both'
guess holds for grep only.
Why not: raw here is 268 files an agent can open in 1-2 reads, so an index
only adds its own page to every turn; and the offered section is the settler
for only some questions. What would: a corpus raw cannot be walked in 1-2
reads, or an entry that carries less per link.

- `walk/`, `grep/`: the first run, three arms each. `*-second-run-*`: the
  `after-2` arm again, rendered after the links were ranked by the brief's own
  facts (3b43130); `walk-leads-6-report.md`: the experiment with 6 links.
- `directories.txt`: top-level directories of both exports and the stems two
  of them share. None on this tree in either arm: this build produced no
  two siblings with one title, so the rename is shown by tests
  (`test_siblings_with_the_same_title_are_named_by_what_each_says`), not by
  this listing.
- When the section an entry offers is the settler, the walk is two reads at
  about the raw cost (q05, q06, q09, q10, q12, q13, q15, q16: 19-22k tokens
  against raw's 18.6k mean). The rest take three to eight reads.
