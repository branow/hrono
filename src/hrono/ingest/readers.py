"""The reader table: one entry per source type.

The contract itself lives in ``hrono.ingest``; this is only the map from a
source's ``type`` to the reader that answers it, in the same shape as the op,
syncer and validator tables. Nothing above this line knows which source type
it is looking at.
"""

from __future__ import annotations

from pathlib import Path

from hrono.ingest import Reader, SplitError, Unit, discovery, pages
from hrono.ingest.bitbucket import bitbucket_instance
from hrono.ingest.confluence import confluence_instance
from hrono.ingest.git_reader import git_instance, git_unit, git_units
from hrono.ingest.github import github_instance
from hrono.ingest.notion import notion_instance

__all__ = [
    "READERS",
    "Reader",
    "Unit",
    "git_instance",
    "git_units",
    "resolve",
]

READERS: dict[str, Reader] = {
    "git": Reader(git_instance, git_units, git_unit),
    "github-user": Reader(
        github_instance,
        discovery.units,
        discovery.unit,
        addresses_as="git",
    ),
    "bitbucket-workspace": Reader(
        bitbucket_instance,
        discovery.units,
        discovery.unit,
        addresses_as="git",
    ),
    "confluence": Reader(confluence_instance, pages.units, pages.unit),
    "notion": Reader(notion_instance, pages.units, pages.unit),
}


def resolve(config: dict[str, object], cache: Path) -> tuple[Reader, str, str]:
    """Return (reader, address type, instance) for a source's config.

    ONE answer to "how is this source read, and how are its pieces addressed",
    because there are two callers — the full split and the incremental update —
    and a source addressed one way by one and another way by the other would
    make every unit look changed on the next diff.
    """
    source_type = str(config["type"])
    reader = READERS.get(source_type)
    if reader is None:
        raise SplitError(f"no reader for source type: {source_type}")
    return (
        reader,
        reader.addresses_as or source_type,
        reader.instance(config, cache),
    )
