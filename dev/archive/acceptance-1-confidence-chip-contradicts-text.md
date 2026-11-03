# A finding's chip contradicts its confidence text (acceptance 1 rerun, 2026-11-03)

What the user did: opened reviewed topic #17 on the flask copy after `hrono tree review`.
What happened: the third finding shows a yellow "medium" chip followed by "high: relies on
Celery's default `get(propagate=True)`...". The stored confidence is "medium-high: relies on...".
Expected: a chip that matches what the model said ("medium-high", or the lower level with the
prose "relies on..." and no stray "high:").
Where: src/hrono/server/ui/reviewed.py:19 `_CONFIDENCE_LINE` takes the first level word and
treats "-" as a separator, leaving "high:" in the prose. Handle "medium-high"/"low-medium" ranges.
Evidence: dev/evidence/acceptance-1/2026-11-03/ev/o2-findings.txt, ui/ui-trees-flask-nodes-17-*.png
