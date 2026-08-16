"""The structure tree the splitter produces: byte-span nodes.

A node is a half-open byte range ``[start, end)`` with a grammar/synthetic type,
a best-effort display name, and children that tile the parent exactly (no gaps,
no overlaps). Parsed nodes carry their grammar type; synthetic delimiter nodes
carry ``~<level>`` (e.g. ``~line``). Because every level tiles its parent, the
leaves in order reproduce the file bytes exactly.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    """A byte-span structure node; children tile ``[start, end)`` exactly."""

    start: int
    end: int
    type: str
    name: str | None
    children: tuple[Node, ...] = ()

    @property
    def synthetic(self) -> bool:
        """Whether this node came from the delimiter cascade, not the parser."""
        return self.type.startswith("~")

    def leaves(self) -> tuple[Node, ...]:
        """Return the childless spans left to right; they tile this node."""
        if not self.children:
            return (self,)
        return tuple(leaf for child in self.children for leaf in child.leaves())
