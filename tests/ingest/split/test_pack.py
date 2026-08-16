from pathlib import Path

import pytest

from hrono.ingest.split import Section, split
from hrono.ingest.split.constants import (
    MIN_PARA,
    PASSAGE_BYTES,
    section_budget,
)

CODE = (
    b"\n\n".join(
        b"def f%d():\n" % i
        + b"\n".join(b"    x%d = %d" % (j, j) for j in range(12))
        for i in range(15)
    )
    + b"\n"
)
PROSE = (
    b"# Title\n\n"
    + b"\n\n".join(
        b"Paragraph %d has a few words in it." % i for i in range(200)
    )
    + b"\n"
).replace(b"\x00", b"")
MINIFIED = b"q" * 40000
CRUMBS = (
    b"A" * 300 + b"\n\nx\n\n" + b"B" * 300 + b"\n\ny\n\n" + b"C" * 300 + b"\n"
)


def _passages(sections: tuple[Section, ...]) -> list:
    return [passage for section in sections for passage in section.passages]


@pytest.mark.parametrize(
    ("name", "raw"),
    [
        ("code.py", CODE),
        ("doc.md", PROSE),
        ("mini.js", MINIFIED),
        ("tiny.py", b"x = 1\n"),
        ("crumbs.txt", CRUMBS),
        (
            "data.json",
            b"{\n"
            + b",\n".join(b'"k%d":%d' % (i, i) for i in range(400))
            + b"\n}\n",
        ),
    ],
)
def test_reassembly_is_byte_identical(name: str, raw: bytes) -> None:
    sections = split(Path(name), raw)
    # sections tile the file, in order
    pos = 0
    for section in sections:
        assert section.start == pos
        pos = section.end
        # a section is the byte-identical concatenation of its passages
        rebuilt = b"".join(raw[p.start : p.end] for p in section.passages)
        assert rebuilt == raw[section.start : section.end]
        # passages tile the section, in order
        inner = section.start
        for passage in section.passages:
            assert passage.start == inner
            inner = passage.end
        assert inner == section.end
    assert pos == len(raw)
    # the whole file reassembles from every passage, in order, no byte lost
    everything = b"".join(raw[p.start : p.end] for p in _passages(sections))
    assert everything == raw


def test_empty_file_yields_no_sections() -> None:
    assert split(Path("empty.py"), b"") == ()


def test_tiny_file_is_one_section_one_passage() -> None:
    raw = b"hello = 1\n"
    sections = split(Path("t.py"), raw)
    assert len(sections) == 1
    assert len(sections[0].passages) == 1
    assert sections[0].start == 0
    assert sections[0].end == len(raw)


def test_section_budget_is_category_based() -> None:
    assert section_budget(Path("a.py")) == 10240
    assert section_budget(Path("a.md")) == 10240
    assert section_budget(Path("a.json")) == 2048
    assert section_budget(Path("a.toml")) == 2048
    assert section_budget(Path("a.csv")) == 2048
    assert section_budget(Path("a.unknown")) == 10240  # default docs


def test_budgets_are_hard_maxima_apart_from_crumb_overshoot() -> None:
    sections = split(Path("code.py"), CODE)
    for section in sections:
        assert section.end - section.start <= 10240 + MIN_PARA
        for passage in section.passages:
            assert passage.end - passage.start <= PASSAGE_BYTES + MIN_PARA
    # a data file uses the smaller 2 KB section budget
    data = (
        b"[\n" + b",\n".join(b'  {"i": %d}' % i for i in range(500)) + b"\n]\n"
    )
    for section in split(Path("d.json"), data):
        assert section.end - section.start <= 2048 + MIN_PARA


def test_min_group_lets_a_real_unit_stand_alone() -> None:
    # each function body is well over MIN_GROUP, so functions do not glue
    # together: roughly one passage per function.
    passages = _passages(split(Path("code.py"), CODE))
    assert len(passages) >= 15
    # by contrast, tiny statements below MIN_GROUP pack together
    small = b"\n".join(b"a%d = %d" % (i, i) for i in range(60)) + b"\n"
    dense = _passages(split(Path("small.py"), small))
    assert len(dense) < 60


def test_byte_chop_splits_an_atomic_span_into_marked_raw_parts() -> None:
    sections = split(Path("mini.js"), MINIFIED)
    passages = _passages(sections)
    assert len(passages) > 1
    assert all(p.part is not None and p.of is not None for p in passages)
    # within a section the chop is numbered 1..n of n
    for section in sections:
        count = len(section.passages)
        assert [p.part for p in section.passages] == list(range(1, count + 1))
        assert all(p.of == count for p in section.passages)
    # every chopped piece is within the passage budget, and nothing is lost
    assert all(p.end - p.start <= PASSAGE_BYTES for p in passages)
    assert b"".join(MINIFIED[p.start : p.end] for p in passages) == MINIFIED


def test_ordinary_passages_carry_no_raw_part_markers() -> None:
    passages = _passages(split(Path("code.py"), CODE))
    assert all(p.part is None and p.of is None for p in passages)


def test_sub_min_para_crumbs_merge_into_a_neighbour() -> None:
    sections = split(Path("crumbs.txt"), CRUMBS)
    for section in sections:
        if len(section.passages) > 1:
            for passage in section.passages:
                assert passage.end - passage.start >= MIN_PARA
    # the crumbs ("x", "y") are not lost — reassembly still exact
    everything = b"".join(CRUMBS[p.start : p.end] for p in _passages(sections))
    assert everything == CRUMBS
