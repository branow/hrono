# Acceptance 1: reviewed topic page scrolls sideways at 390

What the user did: opened topic #17 (extended by insights) on a 390-wide
phone, light and dark.

What happened: the page is 677 px wide (#18: 533 px). A finding's confidence
is model prose ("high; the code path in make_config is unconditional",
"medium; checking the repository's 'publish' environment protection rules
would settle it"). It renders in `span.chip.plain` without wrapping, so the
statement, placement and evidence lines are cut off on the right.

Expected: no horizontal scroll at 390 (goal quality bar). Long confidence
text wraps, or the level word (high/medium/low) is the chip and the reason
plain text.

Evidence: `dev/evidence/acceptance-1/topic/ins-390-light.png`,
`ui/ui-trees-flask-nodes-17-tree-flask-390-*.png`, `ui/report.json`
(sideways-scroll).
