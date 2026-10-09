"""Live job progress as Server-Sent Events.

SSE and not a WebSocket because this is one-way. Nothing the client sends
matters, so a socket buys a handshake, a second protocol and a
reconnect story in exchange for nothing.

The stream POLLS and holds no database connection between polls. A watcher that
kept one open would hold the single writer's shared lock for as long as someone
left a terminal window open, which is a way to wedge the server by being
interested in it.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import AsyncIterator

from starlette.concurrency import run_in_threadpool

from hrono.jobs import store
from hrono.jobs.aggregate import rollup
from hrono.jobs.model import JobStatus

# Fast enough that a person watching does not feel it, slow enough that a
# forgotten terminal is not a load. The job's own work dwarfs it either way.
POLL_SECONDS = 0.5

_TERMINAL = frozenset(
    {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED}
)


def state_of(conn: sqlite3.Connection, job_id: str) -> dict[str, object] | None:
    """The job's current status and progress, or None if it is gone.

    The DERIVED status, so a watcher of a fan-out sees `partial` and the
    children's counts rather than the parent row's own stale `pending`.
    """
    row = store.get(conn, job_id)
    if row is None:
        return None
    rolled = rollup(
        [str(child["status"]) for child in store.children(conn, job_id)]
    )
    state: dict[str, object] = {
        "id": job_id,
        "status": rolled.status if rolled is not None else str(row["status"]),
    }
    if rolled is not None:
        state["progress"] = {"done": rolled.done, "total": rolled.total}
    return state


def is_terminal(state: dict[str, object]) -> bool:
    """Whether the watch may end: the outcome is decided AND nothing is left.

    A parent's status goes terminal the moment one child FAILS — the run cannot
    now succeed, which is the right answer for `GET /jobs/<id>`. It is the
    wrong moment to close a WATCH: the stream would end at `failed 1/2` while
    the other stage is still writing, and a watcher who acts on that acts on a
    database still being changed.

    So a parent's stream also waits for its children to finish. The status it
    ends on is the same; what changes is that "the stream ends when the job
    does" is true.
    """
    if str(state["status"]) not in _TERMINAL:
        return False
    progress = state.get("progress")
    if not isinstance(progress, dict):
        return True  # a leaf: its own status is the whole story
    return progress["done"] == progress["total"]


def frame(state: dict[str, object]) -> str:
    """One SSE frame: a named event and its JSON payload."""
    return f"event: state\ndata: {json.dumps(state)}\n\n"


async def stream(database: object, job_id: str) -> AsyncIterator[str]:
    """Emit the job's state on every change, then end when it is done.

    The CURRENT state goes out immediately, so a client that connects to a job
    already finished gets its answer and a closed stream rather than a hang —
    which is the difference between "watch" being usable in a script and not.
    """
    last: dict[str, object] | None = None
    while True:
        state = await run_in_threadpool(_read, database, job_id)
        if state is None:
            return  # the job was deleted out from under the watcher
        if state != last:
            yield frame(state)
            last = state
        if is_terminal(state):
            return
        await asyncio.sleep(POLL_SECONDS)


def _read(database: object, job_id: str) -> dict[str, object] | None:
    with database.connect() as conn:  # type: ignore[attr-defined]
        return state_of(conn, job_id)
