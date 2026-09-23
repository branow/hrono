"""Ingest: bring a source's current content into the cache and read it.

The CONTRACT every source type implements lives here, at the root of the
package, so a per-type module (#142's syncers, #143's readers) and the ops that
call them can share it without importing each other. ``SyncError`` sits here
for the reason ``ClusterError`` sits in ``cluster/__init__``.

What ``split`` needs from a source is not files: it is a sequence of
addressable UNITS, each with an identity inside the source and the bytes to
split. Git's units are the ingestable files of its working tree; a discovery
source's are the files of every repo it found (#147); a wiki's would be its
pages.

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
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from hrono.errors import DomainError


class SyncError(DomainError):
    """A source could not be synced (reason is credential-free)."""

    code = "sync-error"


class SplitError(DomainError):
    """A source could not be split (reason is credential-free)."""

    code = "split-error"


@dataclass(frozen=True)
class Unit:
    """One addressable piece of a source: its identity and its bytes.

    ``version`` overrides the source's own, for a source whose pieces move
    independently (#147): a discovery source holds many repos, and a repo that
    did not change must not be re-ingested because a sibling did.
    """

    path: str
    body: bytes
    version: str | None = None


@dataclass(frozen=True)
class Reader:
    """How one source type presents itself to the ingest ops.

    ``instance`` is the addressable identity of the source itself — the host
    and path a git url reduces to, an owner root for a discovery source — and
    is the reader's to derive, because only the reader knows the shape of its
    own config. ``units`` enumerates the whole source, which a full split and
    the diff's current side both need; ``unit`` fetches ONE by path, which is
    what the incremental path needs: a diff naming three changed units must not
    re-read the other nine thousand.

    ``addresses_as`` is the source type a unit's URI carries, when that is not
    the source's own: a ``github-user`` source's files are git content that was
    merely FOUND through the provider API, and the spec is explicit that
    discovery is never a piece's address (#147). Left None, a unit is addressed
    as the type that produced it.
    """

    instance: Callable[[dict[str, object]], str]
    units: Callable[[dict[str, object], Path], Iterator[Unit]]
    unit: Callable[[dict[str, object], Path, str], Unit]
    addresses_as: str | None = None
