"""E018: a brief's facts link to the section pages that state them."""

import pytest

from hrono.export.citations import cite

PAGES = {
    "a/fusion.md": "RRF k is 60 and TAU 0.70 for `fuse_ranks`.\n",
    "a/env.md": "Set HRONO_HOME to move the data.\n",
    "a/misc.md": "nothing here\n",
}
LINK = {path: f"../{path}" for path in PAGES}


def run(text: str, pages=PAGES) -> str:
    return cite(text, pages, link={p: f"../{p}" for p in pages})


@pytest.mark.parametrize(
    ("line", "linked"),
    [
        ("Weights use TAU 0.70 throughout.", "[§](../a/fusion.md)"),
        ("Set HRONO_HOME first.", "[§](../a/env.md)"),
        ("Call `fuse_ranks` here.", "[§](../a/fusion.md)"),
        ("The constant is 60 today.", "[§](../a/fusion.md)"),
    ],
    ids=["decimal", "env-name", "code-span", "number"],
)
def test_a_line_stating_a_fact_links_its_section(
    line: str, linked: str
) -> None:
    assert run(line) == f"{line} ({linked})"


def test_a_fact_in_no_section_is_not_linked() -> None:
    line = "The limit is HRONO_MISSING."
    assert run(line) == line


def test_a_fact_found_in_too_many_sections_is_not_linked() -> None:
    pages = {f"p{n}.md": "TAU 0.70\n" for n in range(4)}
    assert run("It is TAU 0.70 here.", pages) == "It is TAU 0.70 here."


def test_at_most_two_sections_are_linked_best_first() -> None:
    pages = {
        "x.md": "TAU 0.70 and HRONO_HOME",
        "y.md": "TAU 0.70",
        "z.md": "HRONO_HOME TAU 0.70",
    }
    out = run("TAU 0.70 and HRONO_HOME", pages)
    assert out.endswith("([§](../x.md), [§](../z.md))")


@pytest.mark.parametrize(
    "text",
    [
        "# TAU 0.70",
        "| TAU 0.70 | x |",
        "```\nTAU 0.70\n```",
    ],
    ids=["heading", "table-row", "fenced"],
)
def test_headings_tables_and_code_are_left_alone(text: str) -> None:
    assert run(text) == text


def test_a_number_inside_a_longer_one_is_not_a_match() -> None:
    assert run("It is 6.", {"a.md": "160"}) == "It is 6."
    assert run("It is 60 wide.", {"a.md": "1600"}) == "It is 60 wide."


def test_the_trailing_newline_is_kept() -> None:
    assert run("plain\n") == "plain\n"
    assert run("plain") == "plain"


def test_a_number_that_is_the_tail_of_a_version_is_not_a_match() -> None:
    assert run("It is 60 wide.", {"a.md": "v1.60"}) == "It is 60 wide."
