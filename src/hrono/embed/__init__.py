"""Embedding: turn stored content into vectors, content-addressed and once.

``embed`` is a job op that loads a local embedding model and stores a vector per
unique content hash, keyed by ``(content_hash, model_name)`` so identical bytes
embed once and a model swap re-embeds without touching the old vectors.
"""
