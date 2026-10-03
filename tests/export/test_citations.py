"""E018: a brief's facts link to the section pages that state them."""

import time

import pytest

from hrono.export.citations import cite

PAGES = {
    "a/fusion.md": "RRF k is 60 and TAU 0.70 for `fuse_ranks`.\n",
    "a/env.md": "Set HRONO_HOME to move the data.\n",
    "a/misc.md": "nothing here\n",
}


def run(text: str, pages=PAGES) -> str:
    return cite(text, pages, link=lambda path: f"../{path}")


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


def test_a_number_that_heads_a_decimal_or_ends_a_sentence_is_a_match() -> None:
    # the word index holds the head of a run before each dot
    assert run("It is 60 wide.", {"a.md": "ratio 60.5 here"}) == (
        "It is 60 wide. ([§](../a.md))"
    )
    assert run("It is 60 wide.", {"a.md": "wide: 60. Then"}) == (
        "It is 60 wide. ([§](../a.md))"
    )


def test_a_fact_with_a_unit_is_a_match_only_as_a_whole_token() -> None:
    line = "Cache is 64 KB."
    hit = {"a.md": "the cache holds 64 KB of rows"}
    assert run(line, hit) == f"{line} ([§](../a.md))"
    assert run(line, {"a.md": "x64 KB"}) == line
    assert run(line, {"a.md": "v1.64 KB"}) == line
    assert run(line, {"a.md": "64 KBs"}) == line


def test_a_subtree_filter_offers_only_its_own_sections() -> None:
    out = cite(
        "Set HRONO_HOME first.",
        PAGES,
        link=lambda path: path,
        within={"a/fusion.md"},
    )
    assert out == "Set HRONO_HOME first."


def test_a_big_corpus_is_cited_quickly() -> None:
    # qa: a fact was searched for in every section on every line of every node,
    # 8 s on 268 sections; a fact is now looked up once. Measured here: 0.03 s.
    pages = {
        f"s{n}.md": " ".join(
            f"HRONO_SET_{n} v{k}.{n} `call_{k}`" for k in range(80)
        )
        + " filler" * 600
        for n in range(300)
    }
    text = "\n".join(
        f"Line {n} sets HRONO_SET_{n % 300}, 1.{n % 300} and `call_{n % 80}`."
        for n in range(3000)
    )

    started = time.perf_counter()
    out = cite(text, pages, link=lambda path: path)
    elapsed = time.perf_counter() - started

    assert "[§](s5.md)" in out
    assert elapsed < 2.0
