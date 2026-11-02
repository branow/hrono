# E059 followups (qa round 2)
- src/hrono/summarize/briefs.py:699 `_keep_replaced` keeps the newest 5 versions plus the first insights version ever; a root passed more than 5 times since its last rewrite, after an earlier pass, loses its cheaper brief and `cheaper_text` (briefs.py:735) then returns an intermediate pass output, so root.md drops the earlier passes' lines; keep the oldest insights version since the last non-insights one instead of the first ever.
(po 2026-11-02: folded into E060 ticket 2.)
