"""The git reader: the ingestable files of a synced working tree.

The filter rules are git's, not ingest's: globs, a size gate, symlinks
and a null-byte sniff all describe a filesystem, and a source type without one
answers the same contract a different way.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from hrono.ingest import Unit
from hrono.ingest.filter import ingestable


def git_units(config: dict[str, object], cache: Path) -> Iterator[Unit]:
    """Every ingestable file in the synced working tree, in path order."""
    filter_config = config.get("filter")
    paths = ingestable(
        cache, filter_config if isinstance(filter_config, dict) else None
    )
    for path in paths:
        yield git_unit(config, cache, path)


def git_instance(config: dict[str, object], cache: Path) -> str:
    """The host+path a git url reduces to, free of scheme and credentials."""
    text = str(config["url"]).strip()
    if "://" in text:
        text = text.split("://", 1)[1]
    head = text.split("/", 1)[0]
    if "@" in head:
        text = text[text.index("@") + 1 :]
    text = text.rstrip("/")
    if text.endswith(".git"):
        text = text[:-4]
    slash = text.find("/")
    colon = text.find(":")
    if colon != -1 and (slash == -1 or colon < slash):
        text = text[:colon] + "/" + text[colon + 1 :]
    return text


def git_unit(config: dict[str, object], cache: Path, path: str) -> Unit:
    """One file of the synced working tree, by its repo-relative path."""
    return Unit(path, (cache / path).read_bytes())
