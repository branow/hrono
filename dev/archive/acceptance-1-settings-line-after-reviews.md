# The insights line reads wrong once everything is reviewed (acceptance 1 rerun, 2026-11-03)

What the user did: after `hrono tree review flask`, opened Settings > Trees > edit flask.
What happened: "Every topic over the threshold is reviewed.. A subscription is not billed per call."
Expected: one sentence of state, e.g. "Every topic over the threshold has been reviewed; a sync
reviews a topic again when it rewrites its brief." No double period, no billing note when
nothing would run (the uk text already says "уже переглянуто", already reviewed).
Where: src/hrono/server/templates/config.html:192 appends "." after a message that ends in one
and keeps the subscription sentence for a zero count.
Evidence: dev/evidence/acceptance-1/2026-11-03/ui/settings-after-review-1440.png
