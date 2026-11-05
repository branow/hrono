You are reviewing two independent attempts, A and B, at the same change to
webERP, an open-source PHP ERP. You do not know how either attempt was
produced; judge only the diffs.

Files given to you (read all of them before scoring):
- task.md: the task both attempts were given.
- checklist.md: what a complete change must get right. It may note that
  the reference is itself incomplete; where it does, grade against the
  task and the checklist, not the reference.
- reference.diff: the change the webERP maintainers merged.
- A.diff and B.diff: the two attempts, as diffs against the same base.
- base/: the webERP source at the base commit, to check what a diff
  touches or misses.

Score each attempt separately and independently (do not rank them against
each other before scoring each):

1. checklist: for every numbered item, met (1), partly (0.5) or missed (0),
   with one line of evidence (file and what it does or lacks). Items the
   checklist marks "reference only, not required" are not scored.
2. correctness 0-5: would the change work as the task asks, in webERP,
   at runtime (undefined functions, wrong variables, broken SQL, wrong
   amounts or signs all count against it).
3. conventions 0-5: does it do things the way webERP does them elsewhere
   (database upgrade scripts and their helpers, the install schema, page
   structure and security tokens, __() strings, shared functions rather
   than copies).
4. regressions: anything it breaks that worked before, listed (or "none").
5. one paragraph of justification.

Answer with this JSON and nothing else:
{"A": {"checklist": {"1": [score, "evidence"], ...}, "checklist_total": n,
       "correctness": n, "conventions": n, "regressions": ["..."],
       "justification": "..."},
 "B": {same shape}}
