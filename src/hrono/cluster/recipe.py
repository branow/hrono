"""The clustering recipe, scaled to the point count.

`how-hrono-works.md` requires the SAME UMAP -> HDBSCAN -> attachment pipeline at
every level, "with dimensions and ``min_cluster_size`` scaled to the point
count (e.g. UMAP-10, ``min_cluster_size=3`` at tens of topics)" — the settled
leaf recipe (UMAP-25, ``min_cluster_size=5``) describes the thousands of
sections at the bottom, not the handful of briefs near the root.

The scaling is data: a ladder of rungs, each with the point count it needs.
UMAP's spectral init asks for ``n_components + 1`` eigenvectors of an N-point
graph, so a rung is only usable at ``N >= n_components + 2`` (measured:
UMAP-25 fails at N = 26 and works at N = 27, `.e2e/artifacts/umap-threshold.md`)
and ``n_neighbors`` must stay below N as well. Each rung therefore applies from
its own floor up, and the largest rung the point count can serve wins: the
settled recipe keeps running wherever it is valid, and a level too small for it
drops to the spec's smaller one rather than to unscaled parameters.

Below the smallest rung there is no honest reduction left — that level cannot be
clustered. That is a ``TooFewPoints``, the one clustering failure a caller may
answer by collecting: ``build-tree`` reads it as "the current top is the root"
and the ``cluster`` op as "then the corpus is one topic" (#112). It is a
distinct type precisely so neither of them catches a BROKEN backend by mistake.
"""

from __future__ import annotations

from dataclasses import dataclass

from hrono.cluster import TooFewPoints


@dataclass(frozen=True)
class Recipe:
    """UMAP + HDBSCAN parameters for one point-count band."""

    min_points: int
    n_components: int
    n_neighbors: int
    min_cluster_size: int


LADDER: tuple[Recipe, ...] = (
    Recipe(min_points=27, n_components=25, n_neighbors=15, min_cluster_size=5),
    Recipe(min_points=12, n_components=10, n_neighbors=10, min_cluster_size=3),
)

MIN_POINTS = LADDER[-1].min_points


def recipe_for(points: int) -> Recipe:
    """Return the largest recipe ``points`` vectors can support."""
    for recipe in LADDER:
        if points >= recipe.min_points:
            return recipe
    raise TooFewPoints(f"too few vectors to cluster: {points} < {MIN_POINTS}")
