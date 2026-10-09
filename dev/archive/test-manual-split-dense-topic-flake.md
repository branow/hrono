# test_a_topic_that_does_not_divide_is_refused_and_left_intact failed once

What: tests/server/test_manual_split.py::test_a_topic_that_does_not_divide_is_refused_and_left_intact
(line 161, the 422 assertion) failed once in a full `pytest -n auto` run during
E017 round 1. The failure output was not kept.

Where: the test builds 14 identical vectors and expects the real HDBSCAN
recipe to find no density core. Identical points are degenerate input for
UMAP, so the outcome may depend on numerics or thread timing.

Not reproduced: E017 round 2 ran tests/server/test_manual_split.py,
test_ui_surgery.py and tests/cluster 16 times under -n auto, and 18 more
runs of the module concurrently (6 at a time, load above 20). 34 runs, all green.

Why it matters: a rare red in the gate costs a qa round. If it recurs, keep the
full failure text (the response body says which branch refused) and replace the
identical vectors with a fixture whose "no division" outcome does not rest on a
degenerate reduction.
