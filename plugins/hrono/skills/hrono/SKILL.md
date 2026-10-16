---
name: hrono
description: Use whenever the session says this project has an hrono map and the question is about what the project's sources hold - an area of a codebase, a system's documentation, how parts fit, where something is. Walks the exported map from the overview down to the source files.
allowed-tools: [Read, Glob, Grep]
---

# hrono - read the map

The map is already exported; the session's opening note gives its folder.
It is a tree of briefs over whatever the tree was built from: repositories,
documentation, wikis. A leaf brief states what its sources do exactly: the
checks that guard each entry point with their conditions, every branch and
the state it sets, what happens on each error, what it sends and receives,
and which other parts it connects to. One brief replaces many file reads.

1. Grep the export's `brief.md` files for the components, names, statuses
   and terms in the question, and read in full the leaf briefs that match.
2. Read the `brief.md` of the folder above each leaf you read. Its `Flows`
   name every part a piece of work passes through, step by step, and what
   each does when a step fails.
3. Follow the work to its end before reading code: every part that
   receives it after the one you found, what each does when it fails, and
   what retries or repairs it - or that nothing does. Read those parts'
   briefs too, from the flows and from each leaf's `## Connected topics`:
   the topics it exchanges work or records with, wherever they sit in the
   map. A repair job often lives in another area than what it repairs.
4. A leaf ends with `## Sources`: the files it was written from. Open them
   to confirm the claims you will make; where the code and a brief
   disagree, the code wins.
5. In the answer, give every part you found on the path its own behaviour.
   Where two parts do the same job - an old and a new consumer, two paths
   for one piece of work - say how each one behaves; they rarely match, and
   "it does the same" loses what the question is about.

For an overview, read `root.md` and the `## Children` it lists. Passages
that match the prompt also arrive attached automatically as "hrono recall".

If no export exists, use hrono-export.
