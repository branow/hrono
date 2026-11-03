# flaky: tests/server/test_ui_browser.py::test_a_live_run_with_a_stage_done_reads_running_never_partial

Failed once in E064 qa's full run (`uv run pytest -n auto`, 2026-11-03, epic/E064
at 317990a), param `[/ui/jobs/going-#run .status, .status-#run .progress]@browser-0`;
passed alone right after (3 passed). E064 does not touch the run page or its
status script. Likely a timing race between the live progress poll and the
assertion under -n auto load; make the test wait on the element state, not
the clock.

(po 2026-11-03: folded into E064 round 2.)
