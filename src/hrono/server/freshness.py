"""Is the tree up to date with its sources (#215).

A source is up to date when the commit its last sync pinned is still where the
remote's HEAD is. That needs one question put to the remote, so it is put once
per source per minute, together, and a remote that does not answer in time is
reported as one that could not be compared rather than as either answer: a page
that said "up to date" for a source it could not reach would be the worst
thing this one could say.

Only a git source can be compared this way. The others report when they were
last read and say they were not compared.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from hrono.crypto.cipher import Cipher
from hrono.db.database import Database
from hrono.ingest.remote_head import remote_head
from hrono.registry import store as registry_store
from hrono.registry.collections.sources import SOURCES
from hrono.registry.collections.trees import scoped_sources
from hrono.registry.write import decrypt

Probe = Callable[[dict[str, object], float], str | None]

# Long enough for a slow remote to answer, short enough that a dead one does
# not hold the front page: the sources are asked at once, so this is the most
# the page can wait however many there are.
TIMEOUT = 4.0
FRESH_FOR = 60.0
_COMPARABLE = frozenset({"git"})


@dataclass(frozen=True)
class SourceState:
    name: str
    kind: str
    read_at: str | None
    commit: str | None
    # current | behind | unread | unreachable | not-compared
    state: str


class Heads:
    """The remotes' current commits: asked together, remembered briefly."""

    def __init__(
        self,
        probe: Probe = remote_head,
        *,
        fresh_for: float = FRESH_FOR,
        timeout: float = TIMEOUT,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._probe = probe
        self._fresh_for = fresh_for
        self._timeout = timeout
        self._clock = clock
        self._seen: dict[tuple[str, str], tuple[float, str | None]] = {}
        self._lock = threading.Lock()

    def read(
        self, configs: Mapping[str, dict[str, object]]
    ) -> dict[str, str | None]:
        """Each named source's remote commit; None where it was not readable."""
        now = self._clock()
        found: dict[str, str | None] = {}
        stale: dict[str, dict[str, object]] = {}
        with self._lock:
            for name, config in configs.items():
                kept = self._seen.get((name, str(config["url"])))
                if kept is not None and now - kept[0] < self._fresh_for:
                    found[name] = kept[1]
                else:
                    stale[name] = config
        if stale:
            with ThreadPoolExecutor(max_workers=len(stale)) as pool:
                asked = {
                    name: pool.submit(self._probe, config, self._timeout)
                    for name, config in stale.items()
                }
                answers = {n: _answer(f) for n, f in asked.items()}
            with self._lock:
                for name, head in answers.items():
                    self._seen[(name, str(stale[name]["url"]))] = (now, head)
            found.update(answers)
        return found


def _answer(future: object) -> str | None:
    try:
        return future.result()  # type: ignore[attr-defined,no-any-return]
    except Exception:
        return None


def survey(
    database: Database, cipher: Cipher | None, heads: Heads, tree: str
) -> list[SourceState]:
    """Every source the tree is built from: when it was last read, at what,
    and whether its remote has moved since.

    Only the tree's own sources: one the tree does not ingest cannot be
    cleared by syncing the tree, so it is not the tree's to be behind on.

    The registry is read and the lock let go BEFORE the remotes are asked: a
    page waiting on a slow remote must not be holding the database while it
    does (#035).
    """
    with database.connect() as conn:
        pinned = {
            str(row["source"]): row
            for row in conn.execute("SELECT * FROM source_state")
        }
        scope = set(scoped_sources(conn, tree))
        rows = [
            row
            for row in registry_store.list_all(conn, "sources")
            if str(row["name"]) in scope
        ]
    configs = {
        str(row["name"]): _config(row, cipher)
        for row in rows
        if _kind(row) in _COMPARABLE and str(row["name"]) in pinned
    }
    remote = heads.read(configs)
    return [
        _state(row, pinned.get(str(row["name"])), remote, configs)
        for row in rows
    ]


def _state(
    row: sqlite3.Row,
    pinned: sqlite3.Row | None,
    remote: Mapping[str, str | None],
    configs: Mapping[str, object],
) -> SourceState:
    name = str(row["name"])
    kind = _kind(row)
    if pinned is None:
        return SourceState(name, kind, None, None, "unread")
    commit, read_at = str(pinned["version"]), str(pinned["synced_at"])
    if name not in configs:
        return SourceState(name, kind, read_at, commit, "not-compared")
    head = remote.get(name)
    if head is None:
        return SourceState(name, kind, read_at, commit, "unreachable")
    state = "current" if head == commit else "behind"
    return SourceState(name, kind, read_at, commit, state)


def _kind(row: sqlite3.Row) -> str:
    return str(json.loads(row["config"]).get("type", ""))


def _config(row: sqlite3.Row, cipher: Cipher | None) -> dict[str, object]:
    config: dict[str, object] = json.loads(row["config"])
    if row["key_id"] is None or cipher is None:
        return config
    return decrypt(config, SOURCES, cipher, int(row["key_id"]))
