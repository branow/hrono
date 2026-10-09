"""The registered config collections, in one place.

The server mounts a router per collection and seeds each collection's defaults
from this single tuple, so adding a collection is one import here -- and one
module in this folder beside it. The package is named for what it holds,
so `from hrono.registry.collections import COLLECTIONS` reads the same as when
this was a flat module; absolute imports mean the stdlib `collections` is still
the stdlib everywhere, including inside these files.
"""

from __future__ import annotations

from hrono.registry.collections.connections import CONNECTIONS
from hrono.registry.collections.models import MODELS
from hrono.registry.collections.prompts import PROMPTS
from hrono.registry.collections.sources import SOURCES
from hrono.registry.collections.trees import TREES
from hrono.registry.descriptor import Descriptor

COLLECTIONS: tuple[Descriptor, ...] = (
    SOURCES,
    CONNECTIONS,
    MODELS,
    PROMPTS,
    TREES,
)
