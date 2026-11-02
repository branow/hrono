# E060 followups (qa round 1)
- The tree form's insights threshold is blank for a tree saved before E057, so the default is not shown (`src/hrono/server/templates/config.html` form_fields); give the field a placeholder with the default (500,000).
- The Insights tip repeats itself: "each pass is billed, about $2.50 a pass at API prices" (`src/hrono/registry/collections/trees.py:63`); say "each pass is billed, about $2.50 at API prices".
- A pass that fails on a provider error fails the whole run and the run's result does not name the topic, so the topic page shows no failed callout (`src/hrono/server/ui/reviewed.py` `_failed_run` reads only `result`'s "failed" list); name the topic in the stage error or read the run's error too.
- The commits group the UI of all three tickets in one commit (a434ebc); process form only.
- (po 2026-11-02: folded into E061; the commit grouping line is process form, rejected.)
