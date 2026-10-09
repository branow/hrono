import statistics
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


def test_passages_fill_the_budget_instead_of_stopping_at_a_crumb() -> None:
    # a group is flushed by the BUDGET alone, never at MIN_GROUP (100 B):
    # flushing there caps passages at a tenth of their budget — a real corpus
    # packed that way has a 152 B median with 68% under 200 B.
    for name, raw in (("code.py", CODE), ("doc.md", PROSE)):
        sizes = sorted(
            p.end - p.start for p in _passages(split(Path(name), raw))
        )
        median = statistics.median(sizes)
        assert median >= PASSAGE_BYTES / 2, (name, median)
        assert max(sizes) <= PASSAGE_BYTES
        # nothing under 200 B in a corpus whose content is far larger
        assert [s for s in sizes if s < 200] == [], (name, sizes)


def test_a_dense_file_packs_into_few_passages_not_one_per_line() -> None:
    small = b"\n".join(b"a%d = %d" % (i, i) for i in range(60)) + b"\n"
    dense = _passages(split(Path("small.py"), small))
    assert len(dense) <= 2  # ~570 B of content, one passage's worth


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


def test_byte_chop_survives_crumbs_flanking_an_atomic_span() -> None:
    # the minified shape: tiny tokens around a huge atomic
    # span (var / x / = / ; are sub-MIN_PARA crumbs that merge, and must not
    # swallow the byte-chop of the 30 KB blob between them).
    raw = b"var x=" + b"a" * 30000 + b";\n"
    sections = split(Path("min.js"), raw)
    passages = _passages(sections)
    # every passage stays within budget despite the crumb/chop interaction
    assert all(p.end - p.start <= PASSAGE_BYTES for p in passages)
    # the over-budget atomic content is split into part/of-marked passages
    assert any(p.part is not None for p in passages)
    # and nothing is lost
    assert b"".join(raw[p.start : p.end] for p in passages) == raw
    for section in sections:
        rebuilt = b"".join(raw[p.start : p.end] for p in section.passages)
        assert rebuilt == raw[section.start : section.end]


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


# structureless blobs: their only whitespace (a tab) is outside the delimiter
# cascade, so the packer really does reach _chop instead of splitting on a
# delimiter. TABBED's even target (423) falls mid-run, 61 bytes past a tab.
TABBED = b"\t".join(b"A" * 120 for _ in range(7))
UNBROKEN = b"q" * 1805


def test_a_chop_cuts_at_whitespace_not_mid_token() -> None:
    # _chop must back off to whitespace: slicing raw byte offsets yields
    # passages like b'tColor = ', a fragment of an identifier.
    passages = _passages(split(Path("blob.txt"), TABBED))
    assert len(passages) == 2
    assert all(p.part is not None for p in passages)  # really the chop path
    cut = passages[0].end
    assert TABBED[cut - 1 : cut] == b"\t"  # backed off to the token edge
    assert cut != 423  # ... which is NOT where the even target fell
    assert all(p.end - p.start <= PASSAGE_BYTES for p in passages)
    assert b"".join(TABBED[p.start : p.end] for p in passages) == TABBED


def test_a_chop_splits_evenly_rather_than_leaving_a_crumb() -> None:
    # budget-then-remainder chopping ends in a tail no later pass can fold
    # away (1805 B became 800/800/205); parts are sized from what is left.
    sizes = [
        p.end - p.start for p in _passages(split(Path("blob.txt"), UNBROKEN))
    ]
    assert sizes == [602, 602, 601]
    assert max(sizes) <= PASSAGE_BYTES


def test_a_crumb_never_costs_its_neighbour_its_structure(
    tmp_path: Path,
) -> None:
    # a 15 B class header merged forward into an 800 B group, pushing it over
    # budget, and the backstop then byte-CHOPPED that group: a structural run
    # of methods came back as raw parts.
    raw = (
        b"class Contact:\n"
        + b"".join(
            b"    def m%d(self):\n        return %d\n" % (i, i)
            for i in range(40)
        )
        + b"\ndef top():\n    pass\n"
    )
    passages = _passages(split(Path("c.py"), raw))
    assert all(p.part is None for p in passages)  # structure, not raw parts
    assert all(p.end - p.start <= PASSAGE_BYTES for p in passages)
    assert b"".join(raw[p.start : p.end] for p in passages) == raw


def test_a_chop_with_no_whitespace_still_respects_the_budget() -> None:
    # the backoff is bounded: an unbroken blob has no token edge to find, so
    # the hard edge stands rather than the budget being exceeded.
    raw = b"q" * 5000
    passages = _passages(split(Path("blob.js"), raw))
    assert all(p.end - p.start <= PASSAGE_BYTES for p in passages)
    assert b"".join(raw[p.start : p.end] for p in passages) == raw
