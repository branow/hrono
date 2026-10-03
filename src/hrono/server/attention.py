"""The lists behind the Health page's counts (E009, #218).

`triage` says HOW MANY; this says WHICH, and what a person can do about each.
A waiting section carries the topic it would fit best and the score; a stale
brief carries why it is stale; a hand edit carries what it holds and since
when. Each list is capped, because the page is read before it is acted on and
a tree with thousands of waiting sections must still open.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from hrono import naming, pins
from hrono.cluster import incubator
from hrono.cluster import store as cluster_store
from hrono.cluster.blend import combined_vector
from hrono.errors import AppError
from hrono.server import triage
from hrono.summarize import briefs

SHOWN = 50


@dataclass(frozen=True)
class Section:
    """A section that needs a person's eye, and where it would fit best."""

    id: int
    path: str
    topic: int | None
    topic_name: str
    nearest: int | None
    nearest_name: str
    score: float | None


@dataclass(frozen=True)
class Stale:
    node_id: int
    name: str
    level: int
    why: str
    settled: bool = False


@dataclass(frozen=True)
class Held:
    kind: str
    target_id: int
    label: str
    where: str
    reason: str
    since: str


def waiting(
    conn: sqlite3.Connection, tree: str, model: str | None
) -> tuple[int, tuple[Section, ...]]:
    """Parked sections, oldest first, each with the topic it is nearest to."""
    rows = incubator.pending(conn, tree)
    centroids = _centroids(conn, tree, model)
    shown = rows[:SHOWN]
    called = _names(conn, centroids, ())
    return len(rows), tuple(
        _section(conn, called, centroids, model, sid, chash, path, None)
        for sid, chash, path, _ in shown
    )


def misfits(
    conn: sqlite3.Connection, tree: str, model: str | None
) -> tuple[int, tuple[Section, ...]]:
    """Sections placed by rule: the topic each sits in, and the one it is
    nearest to besides."""
    rows = conn.execute(
        "SELECT s.id AS id, s.content_hash AS h, s.path AS path, "
        "m.node_id AS node FROM node_members m "
        "JOIN nodes n ON n.id = m.node_id "
        "JOIN sections s ON s.id = m.section_id "
        "WHERE n.tree = ? AND m.forced = 1 ORDER BY m.node_id, s.id",
        (tree,),
    ).fetchall()
    centroids = _centroids(conn, tree, model)
    called = _names(conn, centroids, [int(row["node"]) for row in rows])
    return len(rows), tuple(
        _section(
            conn,
            called,
            centroids,
            model,
            int(row["id"]),
            row["h"],
            row["path"],
            int(row["node"]),
        )
        for row in rows[:SHOWN]
    )


def topics(conn: sqlite3.Connection, tree: str) -> tuple[tuple[int, str], ...]:
    """Every bottom-level topic a section may be filed in, by name."""
    ids = [
        int(row["id"])
        for row in conn.execute(
            "SELECT id FROM nodes WHERE tree = ? AND level = 0 ORDER BY id",
            (tree,),
        ).fetchall()
    ]
    called = naming.names(conn, ids)
    return tuple((node, called[node]) for node in ids)


def stale(conn: sqlite3.Connection, tree: str) -> tuple[Stale, ...]:
    """The topics the count calls unusable, each with why."""
    ids = triage.unanswerable(conn, tree)
    called = naming.names(conn, ids[:SHOWN])
    return tuple(
        Stale(
            node,
            called[node],
            int(
                conn.execute(
                    "SELECT level FROM nodes WHERE id = ?", (node,)
                ).fetchone()["level"]
            ),
            briefs.stale_why(conn, node),
            briefs.settled(conn, node),
        )
        for node in ids[:SHOWN]
    )


def held(conn: sqlite3.Connection, tree: str) -> tuple[Held, ...]:
    """Every hand edit still holding something in this tree.

    A brief or a parenting pin targets a topic; a membership pin targets a
    section and says which topic it was put in.
    """
    rows = conn.execute(
        "SELECT p.kind AS kind, p.target_id AS target, p.reason AS reason, "
        "p.pinned_at AS at, p.anchor_id AS anchor, s.path AS path "
        "FROM pins p "
        "LEFT JOIN sections s ON p.kind = ? AND s.id = p.target_id "
        "JOIN nodes n ON n.id = CASE WHEN p.kind = ? THEN p.anchor_id "
        "ELSE p.target_id END WHERE n.tree = ? "
        "ORDER BY p.pinned_at DESC, p.kind, p.target_id",
        (pins.MEMBERSHIP, pins.MEMBERSHIP, tree),
    ).fetchall()
    ids = {
        int(row["anchor"] if row["kind"] == pins.MEMBERSHIP else row["target"])
        for row in rows
    }
    called = naming.names(conn, ids)
    return tuple(
        Held(
            kind=str(row["kind"]),
            target_id=int(row["target"]),
            label=str(row["path"])
            if row["kind"] == pins.MEMBERSHIP
            else called[int(row["target"])],
            where=called[int(row["anchor"])]
            if row["kind"] == pins.MEMBERSHIP
            else "",
            reason=str(row["reason"] or ""),
            since=str(row["at"])[:10],
        )
        for row in rows
    )


def release(
    conn: sqlite3.Connection, tree: str, kind: str, target_id: int
) -> None:
    """Hand one held thing back, only if this tree holds it."""
    if not any(
        one.kind == kind and one.target_id == target_id
        for one in held(conn, tree)
    ):
        raise AppError(f"tree {tree} holds no {kind} edit on {target_id}")
    pins.unpin(conn, kind, target_id)


def _centroids(
    conn: sqlite3.Connection, tree: str, model: str | None
) -> dict[int, tuple[float, ...]]:
    if model is None:
        return {}
    return cluster_store.node_centroids(conn, tree, model)


def _names(
    conn: sqlite3.Connection,
    centroids: dict[int, tuple[float, ...]],
    extra: list[int] | tuple[int, ...],
) -> dict[int, str]:
    return naming.names(conn, [*centroids, *extra])


def _section(
    conn: sqlite3.Connection,
    called: dict[int, str],
    centroids: dict[int, tuple[float, ...]],
    model: str | None,
    section_id: int,
    content_hash: str,
    path: str,
    topic: int | None,
) -> Section:
    nearest, score = _nearest(conn, centroids, model, content_hash, path, topic)
    return Section(
        id=section_id,
        path=path,
        topic=topic,
        topic_name=called.get(topic, "") if topic is not None else "",
        nearest=nearest,
        nearest_name=called.get(nearest, "") if nearest is not None else "",
        score=score,
    )


def _nearest(
    conn: sqlite3.Connection,
    centroids: dict[int, tuple[float, ...]],
    model: str | None,
    content_hash: str,
    path: str,
    skip: int | None,
) -> tuple[int | None, float | None]:
    if model is None:
        return None, None
    vector = combined_vector(conn, content_hash, path, model)
    if vector is None:
        return None, None
    scored = [
        (node, sum(a * b for a, b in zip(vector, centre, strict=True)))
        for node, centre in centroids.items()
        if node != skip
    ]
    if not scored:
        return None, None
    return max(scored, key=lambda pair: pair[1])
