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

Read the map from the top down, and read it before any code: a search
over the briefs returns dozens of pages in no useful order, while the
overview names each area in one line.

1. Read `root.md`. Pick every area whose line touches the question, and
   read each one's `brief.md` in full. Its `Flows` name every part a piece
   of work passes through, step by step, what each does when a step fails,
   and the parts elsewhere that repair a step or take the same work.
2. Write down the path: every part the work passes through, from what
   starts it to its last effect (the record applied, the email sent), and
   every part named as a repair or a second path, wherever it sits.
3. Read the leaf brief of every part on that list - the last parts as much
   as the first: the area brief gives each part a line or two and its
   failure handling as one rule, while the leaf gives the exact conditions,
   what it skips and how each step fails. The area's `## Children`
   links them; grep the briefs for a part's name only when it is not
   there. Each leaf's `Part of` line links its area, and its
   `## Connected topics` the parts it exchanges work or records with:
   follow them to the parts your list is missing.
4. Only then open code, to confirm the claims you will make - the files are
   under each leaf's `## Sources` - not to explore. Where the code and a
   brief disagree, the code wins.
5. Before you answer, go down the list: for every part, have you read its
   brief, and can you say what it does when the work arrives, when it
   fails partway, and when the same work arrives twice? A part you have not
   read is one you would guess about, and guesses are where answers go
   wrong: read it. What the area brief says about a part does not count as
   reading it. Having an answer for the first parts is not a reason to
   stop.
6. In the answer, give every part on the path its own behaviour. Where two
   parts do the same job - an old and a new consumer, two paths for one
   piece of work - say how each one behaves; they rarely match, and "it
   does the same" loses what the question is about.

Passages
that match the prompt also arrive attached automatically as "hrono recall".

If no export exists, use hrono-export.
