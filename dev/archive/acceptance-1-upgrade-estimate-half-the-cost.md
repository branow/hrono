# The upgrade notice prices the first sync at half its cost (acceptance 1 rerun, 2026-11-03)

What the user did: opened Home and Health on a fresh copy of the flask bench tree (built 10 Oct),
then pressed sync.
What happened: the notice said "about 25 model calls, about $0.8177 at the API's prices". The
sync made exactly 25 text calls but Usage prices it at ~$1.66 (20 brief + 5 brief-upper,
91.9k out, 295k cache-write tokens).
Expected: an estimate within the "about" range, and rounded ("about $0.82", already noted in
backlog/E064-followups.md).
Where: src/hrono/health/upgrade.py:171 `_priced` costs input/output tokens only
(`price.cost(input, output, 0, 0)`); the real calls pay cache writes, and the new prompt's
briefs ran ~3.9k output tokens each.
Evidence: dev/evidence/acceptance-1/2026-11-03/ev/pre-home-health.txt, ev/usage-after-sync1.txt
