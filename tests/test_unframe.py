"""E018: a topic's name is its subject, not the clause announcing the brief."""

import pytest

from hrono.naming import unframe


@pytest.mark.parametrize(
    ("line", "subject"),
    [
        (
            "These condensations describe the SQLite schema of hrono, a system",
            "SQLite schema of hrono, a system",
        ),
        (
            "What this is: a set of condensed notes on hrono's tree-building",
            "Hrono's tree-building",
        ),
        (
            "This collection is a set of condensed notes on the hrono tree",
            "Hrono tree",
        ),
        (
            "This is a condensed walkthrough of Click's termui subsystem",
            "Click's termui subsystem",
        ),
        (
            "This whole batch is condensed documentation for **Click**, CLI",
            "Click, CLI",
        ),
        (
            "This is the full Click changelog, condensed",
            "Click changelog, condensed",
        ),
    ],
    ids=[
        "describe",
        "what-this-is",
        "collection-is-a-set",
        "walkthrough",
        "whole-batch",
        "is-the-full",
    ],
)
def test_the_announcement_is_dropped_and_the_subject_kept(
    line: str, subject: str
) -> None:
    assert unframe(line) == subject


@pytest.mark.parametrize(
    "line",
    [
        "The recall pipeline fuses vectors",
        "The schema of the db",
        "This is it",
        "Fusion",
    ],
    ids=["no-announcement", "article-and-of", "nothing-left", "single-word"],
)
def test_a_line_that_announces_nothing_is_returned_whole(line: str) -> None:
    assert unframe(line) == line
