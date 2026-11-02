# Acceptance 1: finding evidence stores no source version

What the user did: let a sync run insights passes on the flask copy, then
read the findings rows and the topic page.

What happened: 0 of 39 stored findings have a version in their evidence. It
holds `{file, lines}` only. The pass row's `version` is the node's member
signature, not the source commit. The topic page links evidence lines through
the section's current version (`server/ui/reviewed.py` around line 99), so
after a sync changes the file, the lines point at code the review never read.

Expected: goal O2 and `docs/summarization.md`: "evidence (file, lines,
version)". Each evidence item keeps the commit (or source version) it was
read at, and the page links to that version.

Where it comes from: `summarize/review.py` `_finding` copies whatever keys the
model returns. Neither the review prompt's output nor the parser adds the
version of the file the lookups read.

Evidence: `dev/evidence/acceptance-1/ev/o2-findings.txt`.
