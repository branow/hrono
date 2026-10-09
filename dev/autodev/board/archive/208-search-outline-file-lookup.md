---
id: 208
title: find things — text search, an outline view, file to topic
priority: medium
size: medium
depends_on: []
spec_refs: [REQUIREMENTS.md#4 (25-27)]
---

## Context
The map is the only way in. To find the topic about "token rotation" a person expands circles until they see it, and there is no way to go from a file they know to where hrono filed it.

## Description
A search box in the top bar, on every page: matches topic names and briefs, section paths, and section text (the FTS index recall already keeps). Results are grouped by kind and link to the topic page or the section.

An outline view of the tree as an indented, collapsible list with each topic's name, size and health — the same data as the map, for people who read lists, and the view that still works at 500 topics.

A file lookup: a path (or prefix) lists its sections and the topic each sits in; a parked section says so.

## Acceptance criteria
- [ ] searching a word that appears only in a section's text finds that section and its topic
- [ ] the outline shows the whole tree and each row opens the topic page
- [ ] a file path lists its sections with their topics; an unknown path says it is not ingested
- [ ] all three work for a reader
- [ ] search stays usable on the largest tree available — measured, with the number in the Review log

## Out of scope
Semantic search (that is Ask, #207). Editing from the outline.

## Review log
- 2026-10-03 po: authored from the requirements review and the UI review of the same day, at the user's request.
