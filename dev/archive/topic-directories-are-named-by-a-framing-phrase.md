# export topic directories are named by the brief's framing phrase

What: 15 of the 18 topic directories in hrono's own export begin with a
framing phrase instead of the subject, and are cut at 60 characters before
reaching it: `these-condensations-describe-the-sqlite-schema-of-hrono-a-sy-9`,
`what-this-is-a-set-of-condensed-notes-on-hrono-s-tree-buildi-14`,
`this-collection-is-a-set-of-condensed-notes-on-the-hrono-tre-16`.

Where: export/render.py `_directory` slugs the brief's first line; #212 named
topics by what they are about on the dashboard, but the export path still
takes the raw first sentence.

Why it matters: a directory listing is what an agent sees before it opens any
page, and E004's walk-only run shows agents route by names (raw file names
reached the settler in 19/19 at 1.4 reads; the export in 12-13/19).

Evidence: ls .e2e/eval/runs/2026-10-03/levels-2 on a rebuilt tree, or
.autodev/board/evidence/E004/walk/report.md page paths.
