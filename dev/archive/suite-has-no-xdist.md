# the speed bar says `pytest -n auto` but xdist is not installed

Seen in po review of E006: `uv run pytest -n auto` fails ("unrecognized
arguments: -n"); the serial suite takes 169s (1809 tests). Either add
pytest-xdist to the dev group and make the suite parallel-safe, or restate the
bar. Slowest: tests/cluster/test_build.py::test_recovers_planted_groups_with_full_coverage (12s).
