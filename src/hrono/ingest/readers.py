"""The reader table: what a source type yields to ``split`` (#143, T40).

``sync`` (#142) generalized the WRITE half of ingest — bring content into the
cache and pin a version. This is the READ half. What `split` needs from a
source is not files: it is a sequence of addressable UNITS, each with an
identity inside the source and the bytes to split. Git's units are the
ingestable files of its working tree; a Confluence space's units are its pages.
Nothing above this line knows which.

Two rules the contract carries, because hrono's identity scheme depends on
them:

- a unit's ``path`` is its identity inside the source, and lands verbatim in
  the URI ``<source-type>://<instance>/<path>@<version>``. It is the same
  string across syncs for the same logical unit, or every sync re-ingests the
  whole source as new.
- that path carries an EXTENSION, because the splitters pick a grammar from it
  (``structure``) and the section budget scales by it. A reader over a system
  with no file names still names its units as if it had them
  (``spaces/ENG/onboarding.md``) rather than teaching the splitters a second
  way to choose.

``instance`` is the addressable identity of the source itself — the host and
path a git url reduces to, a site for a wiki — and is the reader's to derive
because only the reader knows the shape of its own config.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from hrono.ingest.filter import ingestable


@dataclass(frozen=True)
class Unit:
    """One addressable piece of a source: its identity and its bytes."""

    path: str
    body: bytes


@dataclass(frozen=True)
class Reader:
    """How one source type presents itself to the ingest ops.

    ``units`` enumerates the whole source — what a full split and the diff's
    current side both need. ``unit`` fetches ONE by path, which is what the
    incremental path needs: a diff naming three changed units must not re-read
    the other nine thousand.
    """

    instance: Callable[[dict[str, object]], str]
    units: Callable[[dict[str, object], Path], Iterator[Unit]]
    unit: Callable[[dict[str, object], Path, str], Unit]


def git_units(config: dict[str, object], cache: Path) -> Iterator[Unit]:
    """Every ingestable file in the synced working tree, in path order."""
    filter_config = config.get("filter")
    paths = ingestable(
        cache, filter_config if isinstance(filter_config, dict) else None
    )
    for path in paths:
        yield git_unit(config, cache, path)


def git_instance(config: dict[str, object]) -> str:
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


READERS: dict[str, Reader] = {"git": Reader(git_instance, git_units, git_unit)}
