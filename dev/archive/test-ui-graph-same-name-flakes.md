# tests/server/test_ui_graph.py::test_two_directories_of_the_SAME_NAME_are_said_once flakes

What: failed once in a full `uv run pytest` on epic/E002 (2026-10-03), passed
on the file alone and three isolated re-runs. The E002 diff does not touch the
graph or that test.
Where: the test writes `UPDATE sections ...` through `browser.conn` while the
`browser` fixture's app may still be running its worker.
Why it matters: a red gate at random costs a round per occurrence. Suspected
(unconfirmed) cause is the #194 shape in CONTRIBUTING "The test harness": a
fixture writing through the adopted connection while the worker polls it.
Check whether the `browser` fixture stops the worker first.
