# Finding statements show raw Markdown backticks (acceptance 1 rerun, 2026-11-03)

What the user did: read the Findings card on reviewed topic #17.
What happened: statements read "The Celery example's `process` task is declared with
`ignore_result=False`..." with the backticks shown, right under a brief that renders the same
identifiers as code.
Expected: inline code rendered as in the brief (escape first, then only backtick spans).
Where: src/hrono/server/templates/node.html:153 prints `f.statement` as plain text; the
confidence prose and placement lines have the same issue.
Evidence: dev/evidence/acceptance-1/2026-11-03/ui/ui-trees-flask-nodes-17-tree-flask-1440-light.png
