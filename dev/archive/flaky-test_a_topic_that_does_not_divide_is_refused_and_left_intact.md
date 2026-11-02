# test_a_topic_that_does_not_divide_is_refused_and_left_intact failed again

What: tests/server/test_manual_split.py::test_a_topic_that_does_not_divide_is_refused_and_left_intact@umap
failed once in the E062 qa full run (`uv run pytest -n auto`, 2347 passed,
2026-11-02, head cf1ef55). It passed alone on the branch and on main. E062
does not touch split or clustering.

History: the same flake was seen once in E017 and archived as not reproduced
(dev/archive/test-manual-split-dense-topic-flake.md).

Fix: replace the 14 identical vectors with a fixture whose "no division"
outcome does not rest on a degenerate UMAP reduction, as that note proposes.
