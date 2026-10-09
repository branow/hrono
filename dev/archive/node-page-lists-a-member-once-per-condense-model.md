---
title: the topic page lists a section once per condense model
priority: low
---
`server/ui/nodes.py:_members` LEFT JOINs `condensations` on content_hash alone,
so a section condensed by two models appears twice in a topic's Sections list
(and its `<li id="section-N">`, added by E011, is duplicated). Seen on a copy of
the local demo database: node 4 has 12 members and renders 24 rows. Found by E011 qa.
Pick one condensation per section (the brief's recorded condense model).
