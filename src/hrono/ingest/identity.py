"""Three identities every section/passage needs before it can be stored.

Pure functions over the split output (#029 tree + #030 pieces) and the source
metadata, with no DB and no network:

- **Address** — a fragment-free URI assembled from four stored parts
  (``source_type``, ``instance``, ``path``, ``version``) and rendered
  ``<source_type>://<instance>/<path>@<version>``. The parts are the source of
  truth; position (byte range, order) is data on the piece, never in the URI.
- **Content hash** — SHA-256 hex of the piece's raw bytes; identical bytes share
  a hash regardless of address (the dedup / embed-once key).
- **Structure path** — the chain of nodes from the file root to a piece's packed
  node(s), each segment ``{type, name?, idx}`` (synthetic ``~<level>`` nodes and
  byte-chop ``raw`` parts included), rendered to a compact ``sp:`` URI by
  ``sp_render``.

The packer (#030) carries only byte ranges, so structure paths are reconstructed
here from the #029 tree and a piece's byte range — equivalent to threading a
trail through the packer, and it keeps the packer pure.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from urllib.parse import quote

from hrono.ingest.split.constants import MIN_PARA
from hrono.ingest.split.node import Node

_WORD = re.compile(r"\w")


@dataclass(frozen=True)
class Address:
    """The four stored parts of a piece's address; ``uri`` renders them."""

    source_type: str
    instance: str
    path: str
    version: str

    @property
    def uri(self) -> str:
        return (
            f"{self.source_type}://{self.instance}/{self.path}@{self.version}"
        )


@dataclass(frozen=True)
class Segment:
    """One structure-path segment: a node's type, display name, and index.

    ``part``/``of`` are set only on a terminal ``raw`` segment marking a
    byte-chopped piece; ``name`` is None for unnamed and synthetic nodes.
    """

    type: str
    name: str | None = None
    idx: int = 0
    part: int | None = None
    of: int | None = None


def content_hash(data: bytes) -> str:
    """Return the SHA-256 hex of raw bytes — the dedup / embed-once key."""
    return hashlib.sha256(data).hexdigest()


def structure_paths(
    root: Node,
    start: int,
    end: int,
    part: int | None = None,
    of: int | None = None,
) -> tuple[tuple[Segment, ...], ...]:
    """Reconstruct a piece's structure path(s) from the tree and byte range.

    Descends while a single child fully contains the range (that node was
    descended into by the packer), then treats the children that fall inside the
    range as the packed group: usually one, several when small siblings shared a
    passage. A byte-chopped piece ends in a ``raw`` segment carrying part/of.
    """
    trail: tuple[Segment, ...] = ()
    node = root
    while True:
        container = _container(node.children, start, end)
        if container is None:
            break
        trail += (_segment(container, node.children),)
        node = container

    if part is not None:
        return (trail + (Segment("raw", part=part, of=of),),)
    if node.start == start and node.end == end:
        return (trail,)  # the piece is exactly this whole node

    group = tuple(c for c in node.children if start <= c.start and c.end <= end)
    members = _members(group)
    if not members:
        return (trail,)
    return tuple(trail + (_segment(m, node.children),) for m in members)


def sp_render(path: tuple[Segment, ...]) -> str:
    """Render a structure path to the compact, reversible ``sp:`` URI."""
    return "sp:/" + "/".join(_label(segment) for segment in path)


def _container(children: tuple[Node, ...], start: int, end: int) -> Node | None:
    return next(
        (c for c in children if c.start <= start and end <= c.end), None
    )


def _members(group: tuple[Node, ...]) -> tuple[Node, ...]:
    worded = tuple(n for n in group if _WORD.search(n.type))
    content = tuple(
        n for n in worded if n.name is not None or n.end - n.start >= MIN_PARA
    )
    return content or worded


def _segment(node: Node, siblings: tuple[Node, ...]) -> Segment:
    idx = sum(
        1
        for s in siblings
        if s.type == node.type and s.name == node.name and s.start < node.start
    )
    return Segment(node.type, node.name, idx)


def _label(segment: Segment) -> str:
    if segment.name is not None:
        label = quote(segment.name, safe="")
        if label[:1] in (".", "~"):
            label = f"%{ord(label[0]):02X}" + label[1:]
    else:
        label = "." + segment.type
    if segment.part is not None:
        return f"{label}[{segment.part}/{segment.of}]"
    if segment.idx:
        return f"{label}[{segment.idx}]"
    return label
