"""Summarisation ops (M4): the map/reduce recipe over the topic tree.

``condense`` is the map stage — it reduces each stored section to its essential
information via one cheap LLM call and caches the result by the section's
content hash, so an unchanged section is never re-condensed and brief rebuilds
stay incremental. The reduce stage (per-cluster ``brief``) and the upper levels
land in later tickets. Recipe vocabulary lives in the prompts, not in code.

``UnreachableTree`` lives here, free of the heavy imports, so a caller can catch
it without importing the tree builder.
"""

from __future__ import annotations


class UnreachableTree(Exception):
    """A built tree has level-0 nodes that no parent edge reaches (#124).

    Raised rather than returned, because the alternative is what this exists to
    stop: ``build_tree`` reporting success over a map whose topics are written
    to the export and linked from nothing. That silent shape produced the three
    worst findings of the September run, and the standing rule since #096 is to
    refuse what cannot be rendered correctly and degrade what can — but never
    to report success for either.
    """
