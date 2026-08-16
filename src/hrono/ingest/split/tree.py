"""Build the whole-file structure tree from parsed bytes.

A file with a grammar parses into a tree-sitter tree, converted node by node so
each node's children tile it exactly: inter-node bytes fold into the preceding
sibling and leading bytes into the first child, so no bytes are lost between
tokens. A parsed leaf still over the passage budget grows synthetic delimiter
children. A file with no grammar is one top span the cascade structures. Every
offset is a byte offset, so the leaves reassemble the file byte-for-byte.
"""

from __future__ import annotations

import re
from pathlib import Path

from tree_sitter import Node as TSNode

from hrono.ingest.split.cascade import deepen
from hrono.ingest.split.constants import PASSAGE_BYTES
from hrono.ingest.split.grammar import parser_for
from hrono.ingest.split.node import Node


def structure(path: Path, raw: bytes) -> Node:
    """Parse ``raw`` into a byte-span structure tree rooted at the file."""
    parser = parser_for(path)
    if parser is None:
        return Node(0, len(raw), "text", None, deepen(raw, 0, len(raw)))
    root = parser.parse(raw).root_node
    return _convert(root, raw, 0, len(raw))


def _convert(node: TSNode, raw: bytes, start: int, end: int) -> Node:
    kids = [
        child for child in node.children if child.end_byte > child.start_byte
    ]
    if not kids:
        grown = deepen(raw, start, end) if end - start > PASSAGE_BYTES else ()
        return Node(start, end, node.type, _name(node), grown)
    children = tuple(
        _convert(kid, raw, span_start, span_end)
        for kid, (span_start, span_end) in zip(
            kids, _bounds(kids, start, end), strict=True
        )
    )
    return Node(start, end, node.type, _name(node), children)


def _bounds(kids: list[TSNode], start: int, end: int) -> list[tuple[int, int]]:
    edges = [start, *(kid.start_byte for kid in kids[1:]), end]
    return list(zip(edges, edges[1:], strict=False))


def _name(node: TSNode) -> str | None:
    for field in ("name", "key"):
        child = node.child_by_field_name(field)
        if child is not None:
            return _decode(child.text).strip('"')[:80]
    if node.type == "section" and node.children:
        head = node.children[0]
        if "heading" in head.type:
            return _decode(head.text).lstrip("#").strip()[:80]
    if node.type == "element":
        match = re.match(rb"<\s*([\w:.-]+)", node.text or b"")
        if match:
            return match.group(1).decode()
    return None


def _decode(text: bytes | None) -> str:
    return (text or b"").decode("utf-8", "replace")
