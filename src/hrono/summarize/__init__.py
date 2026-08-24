"""Summarisation ops (M4): the map/reduce recipe over the topic tree.

``condense`` is the map stage — it reduces each stored section to its essential
information via one cheap LLM call and caches the result by the section's
content hash, so an unchanged section is never re-condensed and brief rebuilds
stay incremental. The reduce stage (per-cluster ``brief``) and the upper levels
land in later tickets. Recipe vocabulary lives in the prompts, not in code.
"""
