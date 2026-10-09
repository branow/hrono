"""Summarisation ops: the map/reduce recipe over the topic tree.

``condense`` is the map stage — it reduces each stored section to its essential
information via one cheap LLM call and caches the result by the section's
content hash, so an unchanged section is never re-condensed and brief rebuilds
stay incremental. The reduce stage is the per-cluster ``brief`` and, above it,
``brief_upper``. Recipe vocabulary lives in the prompts, not in code.

``UnreachableTree`` lives here, free of the heavy imports, so a caller can catch
it without importing the tree builder.
"""

from __future__ import annotations


class UnreachableTree(Exception):
    """A built tree has level-0 nodes that no parent edge reaches.

    Raised rather than returned, because the alternative is what this exists to
    stop: ``build_tree`` reporting success over a map whose topics are written
    to the export and linked from nothing. That silent shape is the worst kind
    of wrong map, and the standing rule is to refuse what cannot be rendered
    correctly and degrade what can — but never to report success for either.
    """
