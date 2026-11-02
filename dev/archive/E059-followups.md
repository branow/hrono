# E059 followups (qa round 1)
- docs/architecture.md:215: the new root-page sentence runs to 104 columns; rewrap to 80 like the lines around it.
- src/hrono/summarize/build_tree.py:125 `total_insights` drops the per-run `tokens`, so a sync's (and build's) `insights` result has no token count; add tokens up like reviews.
- src/hrono/summarize/briefs.py:735 `cheaper_text` returns only the brief the latest pass replaced; a root extended twice with no rewrite between shows only the second pass's lines on root.md; walk back to the last non-insights brief.
- src/hrono/summarize/review.py:322 `insights_threshold or 0`: a tree row stored without the key makes every topic due on every build and sync; fall back to INSIGHTS_THRESHOLD as registry/impact.py:657 does.
(po 2026-11-02: folded into E059 tickets 1 and 3, tokens into E060 ticket 3.)
