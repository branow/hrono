import hashlib
import re
from pathlib import Path

from hrono.ingest.identity import (
    Address,
    Segment,
    content_hash,
    sp_render,
    structure_paths,
)
from hrono.ingest.split import split, structure


def test_uri_is_rendered_from_the_four_stored_parts() -> None:
    address = Address(
        source_type="git",
        instance="github.com/acme/webphone",
        path="src/ContactService.java",
        version="abc123",
    )
    assert address.uri == (
        "git://github.com/acme/webphone/src/ContactService.java@abc123"
    )


def test_uri_carries_no_position_fragment_and_parts_are_authoritative() -> None:
    base = Address("git", "h/o/r", "a/b.py", "v1")
    assert "#" not in base.uri
    moved = Address("git", "h/o/r", "a/b.py", "v2")
    assert moved.uri != base.uri  # changing a part changes the URI


def test_content_hash_is_sha256_of_the_raw_bytes() -> None:
    raw = b"the quick brown fox\nand more\n"
    assert content_hash(raw[4:9]) == hashlib.sha256(raw[4:9]).hexdigest()


def test_identical_bytes_share_a_hash_regardless_of_position() -> None:
    left = b"def f(): return 1\n"
    right = b"xxxdef f(): return 1\n"
    assert content_hash(left) == content_hash(right[3:])
    assert content_hash(b"a") != content_hash(b"b")


def test_sp_render_named_unnamed_indexed_synthetic_and_raw() -> None:
    assert sp_render((Segment("cls", "ContactService", 0),)) == (
        "sp:/ContactService"
    )
    assert sp_render((Segment("class_body", None, 0),)) == "sp:/.class_body"
    assert sp_render((Segment("method", "get", 2),)) == "sp:/get[2]"
    assert sp_render((Segment("block", None, 3),)) == "sp:/.block[3]"
    assert sp_render((Segment("~line", None, 0),)) == "sp:/.~line"
    assert sp_render((Segment("raw", None, 0, part=2, of=5),)) == (
        "sp:/.raw[2/5]"
    )
    full = (
        Segment("class_definition", "ContactService", 0),
        Segment("class_body", None, 0),
        Segment("method", "getByUser", 0),
    )
    assert sp_render(full) == "sp:/ContactService/.class_body/getByUser"


def test_sp_render_percent_encodes_names_and_escapes_leading_markers() -> None:
    assert sp_render((Segment("s", "Heading One", 0),)) == "sp:/Heading%20One"
    assert sp_render((Segment("s", "a/b", 0),)) == "sp:/a%2Fb"
    assert sp_render((Segment("s", ".hidden", 0),)) == "sp:/%2Ehidden"
    assert sp_render((Segment("s", "~weird", 0),)) == "sp:/%7Eweird"
    # idx > 0 renders on a named segment; idx 0 does not
    assert sp_render((Segment("s", "dup", 1),)) == "sp:/dup[1]"


CLASS = (
    b"class Contact:\n"
    + b"".join(
        b"    def m%d(self):\n        return %d\n" % (i, i) for i in range(40)
    )
    + b"\ndef top():\n    pass\n"
)


def _all_paths(path: Path, raw: bytes) -> list[str]:
    tree = structure(path, raw)
    rendered: list[str] = []
    for section in split(path, raw):
        for passage in section.passages:
            for sp in structure_paths(
                tree, passage.start, passage.end, passage.part, passage.of
            ):
                rendered.append(sp_render(sp))
    return rendered


def test_a_whole_node_passage_has_one_path() -> None:
    tree = structure(Path("c.py"), CLASS)
    # the last passage is the whole top() function
    last = split(Path("c.py"), CLASS)[-1].passages[-1]
    paths = structure_paths(tree, last.start, last.end, last.part, last.of)
    assert len(paths) == 1
    assert sp_render(paths[0]) == "sp:/top"


def test_a_passage_over_several_siblings_carries_all_their_paths() -> None:
    tree = structure(Path("c.py"), CLASS)
    multi = [
        structure_paths(tree, p.start, p.end, p.part, p.of)
        for s in split(Path("c.py"), CLASS)
        for p in s.passages
        if len(structure_paths(tree, p.start, p.end, p.part, p.of)) > 1
    ]
    assert multi  # at least one passage grouped several methods
    grouped = multi[0]
    assert len(grouped) > 1
    assert all(sp_render(p).startswith("sp:/Contact/") for p in grouped)


def test_structure_paths_are_unique_per_file() -> None:
    paths = _all_paths(Path("c.py"), CLASS)
    assert len(paths) == len(set(paths))


def test_byte_chop_piece_renders_a_raw_part_tail() -> None:
    raw = b"var x=" + b"a" * 4000 + b";\n"
    tree = structure(Path("m.js"), raw)
    tails = []
    for section in split(Path("m.js"), raw):
        for passage in section.passages:
            if passage.part is not None:
                sp = structure_paths(
                    tree, passage.start, passage.end, passage.part, passage.of
                )[0]
                tails.append(sp_render(sp))
    assert tails
    assert all(re.search(r"/\.raw\[\d+/\d+\]$", tail) for tail in tails)


def test_synthetic_segments_render_in_a_no_grammar_file() -> None:
    raw = (b"one line of prose here\ntwo lines of prose over here now\n") * 40
    paths = _all_paths(Path("notes.xyz"), raw)
    assert any(".~" in p for p in paths)
