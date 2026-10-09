# E018 evidence: export an agent can route

Same tree as E004 (hrono at f3e4853, src + top docs, 268 sections), rebuilt on a
scratch server (haiku condense, sonnet briefs; text models inserted directly,
E016), 22 questions, agent sonnet. Arms levels-2, levels-3, raw (levels-4 was
byte-identical to levels-3 in E004 and is dropped).

Tokens (all sessions, 22 questions):

| run | arm | E004 | E018 before routing (4e71010+1fdb609) | E018 after (d28484f) |
|---|---|---|---|---|
| grep | levels-2 | 619,880 (21/22) | 849,526 (22/22) | 433,528 (21/22) |
| grep | levels-3 | 538,647 (21/22) | 973,608 (22/22) | 381,917 (20/22) |
| grep | raw | 340,982 (21/22) | 299,368 (21/22) | 320,182 (22/22) |
| walk | levels-2 | 857,498 (17/22) | 1,611,832 (19/22) | 1,088,400 (19/22) |
| walk | levels-3 | 765,125 (15/22) | 1,294,629 (20/22) | 757,643 (20/22) |
| walk | raw | 414,901 (21/22) | 400,704 (21/22) | 508,501 (21/22) |

Raw varies 300-340k (grep) and 400-510k (walk) between identical runs: that is
the noise floor. Reads to settler (walk, after): levels-2 4.1, levels-3 4.2, raw 1.5.

- `grep/`, `walk/`: the final measurement. `*-before-routing/`: the same tree
  exported at 1fdb609, where the citations were long links and the root kept its
  full 24 KB brief; it cost MORE than E004 (the links doubled every page).
- `directories.txt`: ticket 1, hrono's own export listing, and page sizes.
- Ticket 2: walk-only, no export-arm answer cites only a root.md or brief.md
  (0 of 44 before and after; grep after: 1 of 44, q07 levels-3, not required).

Result: the export is not cheaper than the raw repository on a corpus this
small (1.6 MB, 268 files that the agent can grep or open directly). See the
epic's Log.
