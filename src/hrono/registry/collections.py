"""The registered config collections, in one place.

The server mounts a router per collection and seeds each collection's defaults
from this single tuple, so adding a collection is one import here.
"""

from __future__ import annotations

from hrono.registry.connections import CONNECTIONS
from hrono.registry.descriptor import Descriptor
from hrono.registry.models import MODELS
from hrono.registry.prompts import PROMPTS
from hrono.registry.sources import SOURCES

COLLECTIONS: tuple[Descriptor, ...] = (SOURCES, CONNECTIONS, MODELS, PROMPTS)
