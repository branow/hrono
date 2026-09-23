"""The syncer table: one entry per source type (#142, T40).

Every source type owes the ``sync`` op the same two things and only these two:
the source's current content in the cache path it is given, and a VERSION
pinned as opaque text. Git gets there with clone/pull and a commit SHA; an
API-backed reader gets there with a pull and a page version or etag. The
transport is the variable, the contract is not — so the op holds no ``if type``
and a new reader is an entry here, exactly as ops, resolvers and validators are
entries elsewhere.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from hrono.ingest.bitbucket import bitbucket_sync
from hrono.ingest.confluence import confluence_sync
from hrono.ingest.git_syncer import git_sync
from hrono.ingest.github import github_sync
from hrono.ingest.notion import notion_sync

Syncer = Callable[[dict[str, object], Path, float], str]

SYNCERS: dict[str, Syncer] = {
    "git": git_sync,
    "github-user": github_sync,
    "bitbucket-workspace": bitbucket_sync,
    "confluence": confluence_sync,
    "notion": notion_sync,
}
