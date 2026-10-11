---
name: hrono
description: Use whenever the session says this project has an hrono map and the question is about what the project's sources hold - an area of a codebase, a system's documentation, how parts fit, where something is. Walks the exported map from the overview down to the source files.
allowed-tools: [Read, Glob, Grep]
---

# hrono - read the map

The map is already exported; the session's opening note gives its folder.
It is a tree of briefs over whatever the tree was built from: repositories,
documentation, wikis.

1. Read `root.md`: what the whole thing is, and its topics under
   `## Children`, each with a one-line summary.
2. Open the `brief.md` of the child that fits; repeat down the tree. Choose
   by the summaries; read two siblings when both could fit.
3. A leaf ends with `## Sources`: the files it was written from. Open them;
   the brief says what they are, the files are the truth.

Grep the export folder when you know a name. Read a brief's `Caution` section
before changing anything in its area. Passages that match the prompt also
arrive attached automatically as "hrono recall".

If no export exists, use hrono-export.
