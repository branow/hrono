"""Clustering: build the path-blended vectors topics are grouped from.

A section's clustering vector blends what it says (content) with where it lives
(file path). ``blend`` produces that combined vector from the two component
vectors; the cluster build reduces and groups them into bottom-level topics.

``ClusterError`` lives here, free of the heavy numeric imports, so the op can
report a missing ``cluster`` extra cleanly without importing ``build``.
"""

from __future__ import annotations

from hrono.errors import DomainError


class ClusterError(DomainError):
    """Clustering could not run (reason is client-safe, never a traceback)."""

    code = "cluster-error"


class TooFewPoints(ClusterError):
    """This level has too few points for any rung of the ladder (#094).

    Its own type because it is the one clustering failure that is not a
    failure: a caller may answer it by COLLECTING — `build_tree` reads it as
    "the current top is the root", and the `cluster` op as "then the corpus is
    one topic" (#112). Every other ``ClusterError`` means the backend broke and
    must still fail the job, so the two must not be caught together.
    """

    code = "too-few-points"
