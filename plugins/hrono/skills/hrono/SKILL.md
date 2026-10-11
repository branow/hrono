---
name: hrono
description: Use for any question about how the current repository is organised, what a part of it does, where something lives, or how pieces fit together, whenever the session says this repository is mapped by hrono. Walks the exported hrono map from the overview down to the source files.
allowed-tools: [Read, Glob, Grep]
---

# hrono - walk the map

hrono keeps a map of this repository: a tree of briefs, from one overview of
the whole system down to topics that each list their source files. The
session's start says where the export is (`<export>`). It is plain Markdown;
read it with Read.

## Step 1: Start at the overview

Read `<export>/root.md`. It says what the system is and lists its top-level
topics under `## Children`, each with a one-line summary.

## Step 2: Go down one level at a time

Pick the child whose summary fits the question and read its `brief.md` (the
link in the list). Each page is the brief of that topic, then its own
`## Children`. Choose by the summaries; do not open every child. If two fit,
read both briefs before going deeper.

A brief's `Caution` section lists the non-obvious hazards of that area. Read
it before changing code there.

## Step 3: At a leaf, open the sources

A leaf topic ends with `## Sources`: the files it was written from, as paths
relative to the repository, under the source and commit they were read at.
Open those files in this repository with Read. The brief tells you what they
do and why; the files are the truth. If the commit is older than the code you
see, trust the code.

## Grep when you know the name

For a known identifier, grep the export (`Grep` over `<export>`) to find the
topic that mentions it, then read that topic's brief and sources.

## Recall is automatic

Prompts are matched against the map by a hook, and the relevant passages
arrive attached to the prompt as "hrono recall". Use them as a starting
point; you do not need to run recall yourself.

## Limits

The map describes the code as of its last export. For a file changed since,
read the file. If `<export>` is missing or the session gives no export path,
the hrono-export skill writes one.
