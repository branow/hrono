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
2. Follow the work end to end before reading code: from each brief's
   connections, find the parts on the other side of each message, call or
   shared record - who sends it, who receives it and what that part does,
   what happens when a step fails and what retries or repairs it - and read
   their briefs too. An upper brief (the `brief.md` of a folder above)
   describes the flows across its parts.
3. A leaf ends with `## Sources`: the files it was written from. Open them
   to confirm the claims you will make; where the code and a brief
   disagree, the code wins.

For an overview, read `root.md` and the `## Children` it lists. Passages
that match the prompt also arrive attached automatically as "hrono recall".

If no export exists, use hrono-export.
