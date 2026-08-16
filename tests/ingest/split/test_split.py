from pathlib import Path

import pytest

from hrono.ingest.split import Node, structure
from hrono.ingest.split.cascade import deepen
from hrono.ingest.split.constants import CASCADE, PASSAGE_BYTES

PY = (
    b"def foo(x):\n    return x\n\nclass Bar:\n    def m(self):\n        pass\n"
)
MD = b"# Heading One\n\nsome text\n\n## Sub Heading\n\nmore words here\n"
PROSE = ("first line\nsecond line\n\n" + ("word " * 400) + "\n").encode()
NO_GRAMMAR = ("alpha\nbeta\n\n" + ("x " * 600) + "\n").encode()
BLOB = b"x" * 2000
BINARY = bytes(range(256)) * 8


def _assert_exact_cover(root: Node, raw: bytes) -> None:
    assert root.start == 0
    assert root.end == len(raw)
    pos = 0
    for leaf in root.leaves():
        assert isinstance(leaf.start, int) and isinstance(leaf.end, int)
        assert leaf.start == pos
        assert leaf.end >= leaf.start
        pos = leaf.end
    assert pos == len(raw)
    assert b"".join(raw[lf.start : lf.end] for lf in root.leaves()) == raw


@pytest.mark.parametrize(
    ("name", "raw"),
    [
        ("code.py", PY),
        ("doc.md", MD),
        ("prose.md", PROSE),
        ("notes.xyz", NO_GRAMMAR),
        ("blob.dat", BLOB),
        ("weird.py", BINARY),
        ("tiny.py", b"hi\n"),
        ("empty.py", b""),
    ],
)
def test_leaves_reassemble_the_file_byte_for_byte(
    name: str, raw: bytes
) -> None:
    _assert_exact_cover(structure(Path(name), raw), raw)


def test_code_file_has_named_grammar_nodes() -> None:
    root = structure(Path("code.py"), PY)
    top = [(child.type, child.name) for child in root.children]
    assert ("function_definition", "foo") in top
    assert ("class_definition", "Bar") in top


def test_grammar_node_names_reach_nested_declarations() -> None:
    root = structure(Path("code.py"), PY)
    names = _collect_names(root)
    assert "foo" in names
    assert "Bar" in names
    assert "m" in names


def test_markdown_section_uses_its_heading_as_the_name() -> None:
    root = structure(Path("doc.md"), MD)
    sections = [c for c in root.children if c.type == "section"]
    assert sections
    assert sections[0].name == "Heading One"


def test_no_grammar_file_still_builds_a_tree_via_the_cascade() -> None:
    root = structure(Path("notes.xyz"), NO_GRAMMAR)
    assert root.type == "text"
    assert root.children
    assert all(child.synthetic for child in root.children)


def test_cascade_deepens_in_order_and_skips_levels_under_two_pieces() -> None:
    # Over budget, no blank line -> level 0 yields one piece and is skipped;
    # the many newlines make level 1 (line) the first level that splits.
    raw = (b"a" * 40 + b"\n") * 30
    children = deepen(raw, 0, len(raw))
    assert {child.type for child in children} == {"~line"}


def test_cascade_falls_through_to_word_when_only_spaces_split() -> None:
    raw = b"word " * 400  # 2000 B, no newlines, no sentence/comma delimiters
    children = deepen(raw, 0, len(raw))
    assert {child.type for child in children} == {"~word"}


def test_cascade_only_deepens_spans_over_the_passage_budget() -> None:
    small_piece = b"tiny\n\n"  # under budget after the blank-line split
    big_piece = b"word " * 400  # 2000 B, no blank line -> must deepen further
    raw = small_piece + big_piece
    small, big = deepen(raw, 0, len(raw))
    assert not small.children
    assert big.children


def test_a_span_with_no_known_delimiter_stays_a_single_leaf() -> None:
    root = structure(Path("blob.dat"), BLOB)
    assert len(root.leaves()) == 1
    assert root.leaves()[0].end - root.leaves()[0].start == len(BLOB)


def test_over_budget_leaves_have_no_delimiter_left_to_split_on() -> None:
    root = structure(Path("blob.dat"), BLOB)
    separators = [d.separator for d in CASCADE]
    for leaf in root.leaves():
        if leaf.end - leaf.start > PASSAGE_BYTES:
            body = BLOB[leaf.start : leaf.end]
            assert not any(sep in body for sep in separators)


def test_cascade_is_data_walked_by_one_routine() -> None:
    assert [d.name for d in CASCADE] == [
        "blank-line",
        "line",
        "sentence",
        "comma",
        "word",
    ]
    assert [d.separator for d in CASCADE] == [
        b"\n\n",
        b"\n",
        b". ",
        b",",
        b" ",
    ]


def _collect_names(node: Node) -> set[str]:
    found = {node.name} if node.name else set()
    for child in node.children:
        found |= _collect_names(child)
    return found
