# Two fast-suite tests flake under load (acceptance 1 rerun, 2026-11-03)

What the user did: ran `uv run pytest -n auto -m "not slow"` in a fresh clone through `heavy`,
machine load ~15 (Spotlight indexing) with a review run going.
What happened: 2 failed, 2194 passed in 53.8 s:
- tests/jobs/test_worker.py::test_health_depends_on_the_beat_actually_coming_round
  (20 ms heartbeat, asserts healthy after three grace windows)
- tests/registry/test_completeness.py::test_the_delete_preview_closes_its_copy
  (gc.collect() then no ResourceWarning in recwarn; may catch another test's connection)
Both pass alone and the whole fast suite passed on a rerun (51.5 s); the full suite was green.
Expected: a contributor's gate does not go red from timing or another test's garbage.
Evidence: dev/evidence/acceptance-1/2026-11-03/ev/fast-suite.txt, ev/fast-suite-2.txt
