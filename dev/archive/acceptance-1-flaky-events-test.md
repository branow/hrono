# Acceptance 1: flaky events stream test in the full suite

What the user did: ran the full suite (`uv run pytest -n auto`, through
`heavy`) on a fresh clone of main.

What happened: `tests/jobs/test_events.py::test_the_stream_follows_a_job_to_its_end`
failed once (2340 passed). It passed three times alone and the full rerun
was green (2341 passed).

Expected: the full suite is green on every run (goal quality bar).
