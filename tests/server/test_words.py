"""#216: counts and sizes said the way a person says them."""

from __future__ import annotations

import pytest

from hrono.server.words import counted, size


@pytest.mark.parametrize(
    ("count", "said"),
    [
        (0, "0 topics"),
        (1, "1 topic"),
        (2, "2 topics"),
        (11, "11 topics"),
    ],
)
def test_a_count_agrees_with_its_noun(count: int, said: str) -> None:
    assert counted(count, "topics") == said


def test_a_count_of_one_section_is_singular() -> None:
    assert counted(1, "sections") == "1 section"


@pytest.mark.parametrize(
    ("count", "said"),
    [(10240, "10 KB"), (2048, "2 KB"), (800, "800 B"), (1500, "1500 B")],
)
def test_a_size_reads_in_the_unit_it_is_budgeted_in(
    count: int, said: str
) -> None:
    assert size(count) == said
