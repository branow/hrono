"""Non-tree edges on the graph: pull, proximity, propagation (T50.3, #184).

The hierarchy is the one relationship the tree already makes obvious. These are
the three that explain why it is WRONG: chunks that belong next door, two
siblings that are really one topic, and the path a change climbed.

Opt-in per URL and computed over the VISIBLE topics only. Two of the three need
centroids, a centroid costs every member vector it is made of, and the default
graph (#183) stays as fast as it was.

The pull comparison is NOT made here: it is `monitor.verdicts`, the same rule
the stored misfit count is made of, so the drawn edge and the number cannot
disagree. Only the candidate set is this module's — the topics on the page.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from hrono.cluster import monitor
from hrono.cluster import store as cluster_store
from hrono.cluster.placement import TAU
from hrono.db.update_log import recent
from hrono.embed.model import resolve_embedding_model
from hrono.errors import DomainError

KINDS = ("pull", "proximity", "propagation")
VECTOR_KINDS = frozenset({"pull", "proximity"})


@dataclass(frozen=True)
class Link:
    """One non-tree edge between two topics on the page."""

    kind: str
    source: int
    target: int
    label: str
    weight: float = 1.0


@dataclass(frozen=True)
class Overlay:
    """What was asked for, what could be drawn, and why not."""

    kinds: tuple[str, ...]
    links: tuple[Link, ...]
    unavailable: str | None = None


def strongest(links: Sequence[Link], cap: int) -> tuple[Link, ...]:
    """At most ``cap`` links, the strongest of each kind taking turns.

    A weight only means something against its own kind: a count of chunks and
    a similarity are not on one scale. So each kind is ranked on its own and
    the kinds are dealt from in rotation, which is what keeps a hundred pull
    arcs from crowding out the one near-duplicate pair.
    """
    if len(links) <= cap:
        return tuple(links)
    ranked = [
        sorted(
            (link for link in links if link.kind == kind),
            key=lambda link: (-link.weight, link.source, link.target),
        )
        for kind in KINDS
    ]
    turns = max((len(group) for group in ranked), default=0)
    dealt = (
        group[turn]
        for turn in range(turns)
        for group in ranked
        if turn < len(group)
    )
    return tuple(link for _, link in zip(range(cap), dealt, strict=False))


def parse(requested: str) -> tuple[str, ...]:
    """The recognised kinds in ``?edges=``, in a stable order."""
    asked = {part.strip() for part in requested.split(",")}
    return tuple(kind for kind in KINDS if kind in asked)


def build(
    conn: sqlite3.Connection,
    tree: str,
    visible: Sequence[int],
    kinds: Sequence[str],
) -> Overlay:
    """The requested edges among the visible topics."""
    if not kinds:
        return Overlay(kinds=(), links=())
    links: list[Link] = []
    unavailable: str | None = None
    if set(kinds) & VECTOR_KINDS:
        try:
            model = str(resolve_embedding_model(conn, {})["name"])
        except DomainError as exc:
            unavailable = str(exc)
        else:
            centroids = cluster_store.node_centroids(conn, tree, model, visible)
            if "pull" in kinds:
                links.extend(_pull(conn, model, centroids))
            if "proximity" in kinds:
                links.extend(_proximity(conn, tree, centroids))
    if "propagation" in kinds:
        links.extend(_propagation(conn, tree, visible))
    return Overlay(
        kinds=tuple(kinds), links=tuple(links), unavailable=unavailable
    )


def _pull(
    conn: sqlite3.Connection,
    model: str,
    centroids: dict[int, tuple[float, ...]],
) -> tuple[Link, ...]:
    """Holder -> the drawn topic whose centroid is nearer, per member count."""
    counts: dict[tuple[int, int], int] = {}
    for verdict in monitor.verdicts(conn, model, tuple(centroids), centroids):
        if verdict.puller is None:
            continue
        key = (verdict.node_id, verdict.puller)
        counts[key] = counts.get(key, 0) + 1
    return tuple(
        Link(
            kind="pull",
            source=holder,
            target=puller,
            label=f"{count} section{'s' if count != 1 else ''} nearer",
            weight=float(count),
        )
        for (holder, puller), count in sorted(counts.items())
    )


def _proximity(
    conn: sqlite3.Connection,
    tree: str,
    centroids: dict[int, tuple[float, ...]],
) -> tuple[Link, ...]:
    """Drawn siblings whose centroids sit at or above TAU: merge candidates.

    Two UNPARENTED leaves are siblings too. A tree with no level above it is
    every tree between the first cluster build and the first brief pass, and
    it is exactly where near-duplicate clusters are worth seeing — a rule that
    required a shared parent would draw nothing there and draw it silently.
    """
    parents = _parents(conn, tree, tuple(centroids))
    drawn = sorted(centroids)
    return tuple(
        Link(
            kind="proximity",
            source=left,
            target=right,
            label=f"{similarity:.2f} similar",
            weight=similarity,
        )
        for index, left in enumerate(drawn)
        for right in drawn[index + 1 :]
        if parents.get(left) == parents.get(right)
        and (similarity := _dot(centroids[left], centroids[right])) >= TAU
    )


def _parents(
    conn: sqlite3.Connection, tree: str, node_ids: Sequence[int]
) -> dict[int, int]:
    if not node_ids:
        return {}
    holes = ", ".join("?" * len(node_ids))
    return {
        int(row["child_id"]): int(row["parent_id"])
        for row in conn.execute(
            "SELECT c.parent_id, c.child_id FROM node_children c "
            "JOIN nodes n ON n.id = c.parent_id "
            f"WHERE n.tree = ? AND c.child_id IN ({holes})",
            (tree, *node_ids),
        ).fetchall()
    }


def _propagation(
    conn: sqlite3.Connection, tree: str, visible: Sequence[int]
) -> tuple[Link, ...]:
    """Where a change climbed to, for the recent decisions of this tree."""
    drawn = set(visible)
    seen: set[tuple[int, int]] = set()
    links: list[Link] = []
    rows, _ = recent(conn, tree)
    for row in rows:
        climbed_to = row["climbed_to"]
        node_id = int(row["node_id"])
        if climbed_to is None or int(climbed_to) == node_id:
            continue
        pair = (node_id, int(climbed_to))
        if pair in seen or not drawn.issuperset(pair):
            continue
        seen.add(pair)
        links.append(
            Link(
                kind="propagation",
                source=node_id,
                target=int(climbed_to),
                label=str(row["action"]),
            )
        )
    return tuple(links)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))
