# E062 followups (qa round 1, minor)

- README sends a CLI admin to `POST /jobs {"op":"settle"}`, which docs/api.md:164 calls "for debugging only", and there is no `hrono tree settle`; README.md:238. Fix: a `hrono tree review <tree>` (or `settle`) CLI command that queues settle and watches it, and the README names it.
- README says "about $2.50 a topic" while the dry run says $2.82 a topic (review + extend); README.md:227. Fix: "about $2.80 a topic (a review and the extend call)".
- After "Review now" the Runs page says "Started settle." (the op name, not what the admin pressed); src/hrono/server/ui/jobs.py:443. Fix: name the reviews when the form came from the insights line (e.g. a `then=review` field).
- Evidence versions are keyed by bare repo path too; in a tree of two sources holding the same path (README.md), the last source's version wins; src/hrono/summarize/review.py:251. Fix: keep the bare-path key only when one source holds it.
