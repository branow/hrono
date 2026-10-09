"""Run one op's independent LLM calls in a bounded pool.

A first build spends nearly all of its wall clock waiting. Measured on a real
corpus: 421 sections, one ``claude-code`` call each at 4-30 s, about 70 minutes
end to end, idle for almost all of it. The calls are independent by
construction — a condensation is keyed by its section's CONTENT HASH and a
brief by its node — so nothing but the shape of the loop made them serial.

What stays serial is the WRITE. The ops already follow one lock discipline: the
lock is taken only for the short persist AFTER a call returns, so the calls move
into a ``ThreadPoolExecutor`` and the persist stays on the CALLING thread, one
at a time, in SUBMISSION order. Two threads are therefore never both inside
``Database.write``, and the op's counts and token totals do not depend on which
call happened to finish first.

Three properties of the serial loop are kept deliberately:

- a failed call does not discard what succeeded. Every result that came back is
  persisted and the FIRST failure in submission order is re-raised once the
  pool has drained, so an idempotent re-run still fills only the gaps.
- a failure stops the op launching MORE calls, and so does a job that no longer
  reads ``running``: ``proceed`` is consulted before every submission, which is
  what keeps a stop from having to wait out all 421 calls.
- nothing is submitted speculatively. At most ``workers`` calls are in flight,
  so an op that stops launching has at most that many left to pay for.

WIDTH is an OPERATIONAL knob — not model config, and not a bare constant. It
belongs to the machine and the account running the server: a laptop driving
``claude`` subprocesses and a CI box holding an API key want different numbers
for the same registered model, so putting it in the ``models`` collection would
store one operator's rate limit as another's config and sync it between them. A
bare constant could not be moved at all by someone meeting a 429. ``hrono
serve`` owns every LLM call in one process, so the process environment is where
it goes: ``HRONO_LLM_CONCURRENCY``, floored at 1.

The default is 4, and the argument is that 4 is affordable as EITHER backend. A
``claude-code`` call is a subprocess and an API call is a socket: four
``claude`` processes fit on a developer laptop, and at the measured 4-30 s per
call four in flight stay inside the 50 requests/minute of the smallest paid
Anthropic tier. It is also the conservative end of useful — those 70 minutes
become about 18 — which is the right side to default on when guessing high
fails as a rate-limit error on work the user has already paid to reach.
"""

from __future__ import annotations

import os
from collections import deque
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor

from hrono.db.database import Database
from hrono.jobs import store
from hrono.jobs.stages import note_item

DEFAULT_WIDTH = 4
ENV_WIDTH = "HRONO_LLM_CONCURRENCY"


def mapped[Item, Made](
    items: Sequence[Item],
    compute: Callable[[Item], Made],
    persist: Callable[[Item, Made], None],
    *,
    workers: int,
    proceed: Callable[[], bool],
    named: Callable[[Item], str] | None = None,
) -> list[Made]:
    """Compute each item in the pool; persist the results one at a time.

    ``compute`` runs on a worker thread and must touch nothing but its own
    item; ``persist`` runs on this thread, in submission order, and is the only
    place a transaction is opened. Returns what was persisted, in that same
    order, so a caller's counts and sums are independent of completion order.
    ``named`` says what an item is, and a failure is noted with it, so
    the run that died can say which section or topic it was on.
    """
    queued = list(items)
    cursor = 0
    stop = False
    failure: BaseException | None = None
    made: list[Made] = []
    inflight: deque[tuple[Item, Future[Made]]] = deque()
    with ThreadPoolExecutor(
        max_workers=workers, thread_name_prefix="hrono-llm"
    ) as pool:
        while True:
            while not stop and cursor < len(queued) and len(inflight) < workers:
                if not proceed():
                    stop = True
                    break
                item = queued[cursor]
                inflight.append((item, pool.submit(compute, item)))
                cursor += 1
            if not inflight:
                break
            item, future = inflight.popleft()
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - re-raised once drained
                if failure is None and named is not None:
                    note_item(exc, named(item))
                failure = failure if failure is not None else exc
                stop = True
                continue
            persist(item, result)
            made.append(result)
    if failure is not None:
        raise failure
    return made


def width() -> int:
    """How many LLM calls one op may have in flight on this server."""
    asked = os.environ.get(ENV_WIDTH)
    if asked is None:
        return DEFAULT_WIDTH
    try:
        return max(1, int(asked))
    except ValueError:
        return DEFAULT_WIDTH


def running(database: Database, job_id: str) -> Callable[[], bool]:
    """A predicate that goes False once ``job_id`` stops reading ``running``.

    A row that is not there at all answers True: ops are called directly by
    tests and by drivers that enqueued nothing, and a missing row is no
    evidence that anyone asked for a stop.
    """

    def alive() -> bool:
        with database.connect() as conn:
            row = store.get(conn, job_id)
        return row is None or row["status"] == "running"

    return alive
