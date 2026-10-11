"""Counts and sizes said the way a person says them."""

from __future__ import annotations

import pytest

from hrono.server.words import counted, size, weight


@pytest.mark.parametrize(
    ("count", "said"),
    [
        (0, "0 topics"),
        (1, "1 topic"),
        (2, "2 topics"),
    ],
)
def test_a_count_agrees_with_its_noun(count: int, said: str) -> None:
    assert counted(count, "topics") == said


@pytest.mark.parametrize(
    ("count", "said"),
    [(10240, "10 KB"), (800, "800 B"), (1500, "1500 B")],
)
def test_a_size_reads_in_the_unit_it_is_budgeted_in(
    count: int, said: str
) -> None:
    assert size(count) == said


@pytest.mark.parametrize(
    ("count", "said"),
    [(32_818_903, "31.3 MB"), (5000, "5 KB"), (800, "800 B")],
)
def test_a_measured_total_reads_rounded(count: int, said: str) -> None:
    assert weight(count) == said
