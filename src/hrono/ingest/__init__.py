"""Ingest: bring a source's current content into the cache and read it.

``SyncError`` lives here, at the root of the package, so the per-type syncers
(#142) and the ``sync`` op can both raise and catch it without importing each
other — the same place ``ClusterError`` sits for the same reason.
"""

from __future__ import annotations


class SyncError(Exception):
    """A source could not be synced (reason is credential-free)."""
