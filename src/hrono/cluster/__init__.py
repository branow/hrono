"""Clustering: build the path-blended vectors topics are grouped from.

A section's clustering vector blends what it says (content) with where it lives
(file path). ``blend`` produces that combined vector from the two component
vectors; the cluster build reduces and groups them into bottom-level topics.

``ClusterError`` lives here, free of the heavy numeric imports, so the op can
report a missing ``cluster`` extra cleanly without importing ``build``.
"""

from __future__ import annotations


class ClusterError(Exception):
    """Clustering could not run (reason is client-safe, never a traceback)."""
