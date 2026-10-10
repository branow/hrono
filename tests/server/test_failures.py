"""A failed run's item, short enough to sit in a heading."""

from __future__ import annotations

from hrono.server.failures import explain


def test_a_batch_names_its_first_item_and_counts_the_rest() -> None:
    whole = "sections a/one.py, b/two.py, c/three.py"

    failure = explain("llm-error", "boom", {"stage": "condense", "item": whole})

    assert failure.item == "sections a/one.py and 2 more"
    assert failure.whole == whole


def test_a_single_item_is_kept_as_it_is() -> None:
    failure = explain("llm-error", "boom", {"item": "sections a/one.py"})

    assert failure.item == "sections a/one.py"
