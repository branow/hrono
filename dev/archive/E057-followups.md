# E057 followups (qa r1, minor)

- Tree field `insights` says "each review is billed, about $2.50 on Opus"; on a claude-code subscription nothing is billed per token (`src/hrono/registry/collections/trees.py:63`): say "about $2.50 at API prices".
- `insights_threshold: true` is stored as 1 (pydantic lax bool to int) (`src/hrono/registry/collections/trees.py:68`): add `strict=True` or a validator refusing bools.
- The dry run lists the root with a pass even when it already had one and 0 characters are unreviewed under it (`src/hrono/summarize/insights.py:90`): E058 should decide whether "the root always" applies on a sync where nothing under the root changed, and the dry run follow.
- `resolve_text_model(conn, {}, "insights")` falls back to the sole text model when no model has the role (`src/hrono/summarize/resolve.py:55`): E058 must refuse to run a pass then (the dry run's note already says nothing runs), not review on the cheap model.
- Dev put tickets 1 and 2 in one commit (21d66ca); process form only.
