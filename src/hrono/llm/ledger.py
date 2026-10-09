"""The usage ledger: one row per model call, written at the one seam.

Tokens recorded only on what a call PRODUCED — a condensation row, a brief row
— leave nothing behind for a call that failed, a call that was retried, or a
judge vote, and no run could say what it had cost. So this records the CALL,
whatever became of it, against the job that made it and the run
a person started.

Both halves of the system come through here: ``Ledgered`` wraps whatever
``Completion`` a model resolves to, and ``metered`` wraps an embedding encoder.
``providers.client_for`` applies the wrapper to every provider it can build,
so a provider added to its map is recorded without anyone remembering to.

A row is written on the calling thread, so a pool of concurrent calls writes
its rows concurrently; each is its own short transaction, the same as any other
writer, and sqlite's write lock serialises them.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from hrono.db.database import Database
from hrono.jobs.ops import JobContext
from hrono.llm.client import Completion, CompletionRequest, CompletionResult


class Tally:
    """Tokens a remote encoder reports for the batch it just embedded.

    The encoder seam returns vectors only, so the provider's own count travels
    beside it: the encoder ``add``s, the ledger wrapper ``take``s once the call
    returns. Local encoders never add, so their rows stay NULL.
    """

    def __init__(self) -> None:
        self._tokens: int | None = None

    def add(self, tokens: int) -> None:
        self._tokens = tokens if self._tokens is None else self._tokens + tokens

    def take(self) -> int | None:
        tokens, self._tokens = self._tokens, None
        return tokens


Clock = Callable[[], float]
Encode = Callable[[list[str]], Sequence[Sequence[float]]]


@dataclass(frozen=True)
class Call:
    """One model call, as the ledger stores it."""

    model: str
    role: str
    provider: str
    upstream_model: str | None
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None
    cache_creation_tokens: int | None
    duration_ms: int
    ok: bool


class Ledgered:
    """A ``Completion`` that records every call it makes, success or not."""

    def __init__(
        self,
        inner: Completion,
        context: JobContext,
        *,
        role: str,
        provider: str,
        clock: Clock = time.monotonic,
    ) -> None:
        self._inner = inner
        self._context = context
        self._role = role
        self._provider = provider
        self._clock = clock

    @property
    def inner(self) -> Completion:
        """The provider's own client, under the recording."""
        return self._inner

    def complete(self, request: CompletionRequest) -> CompletionResult:
        started = self._clock()
        try:
            result = self._inner.complete(request)
        except Exception:
            self._record(request, None, started)
            raise
        self._record(request, result, started)
        return result

    def _record(
        self,
        request: CompletionRequest,
        result: CompletionResult | None,
        started: float,
    ) -> None:
        usage = None if result is None else result.usage
        record(
            self._context.database,
            self._context.job_id,
            Call(
                model=str(request.model.get("name") or request.model["model"]),
                role=self._role,
                provider=self._provider,
                upstream_model=None if usage is None else usage.model,
                input_tokens=None if usage is None else usage.input_tokens,
                output_tokens=None if usage is None else usage.output_tokens,
                cache_read_tokens=None if usage is None else usage.cache_read,
                cache_creation_tokens=(
                    None if usage is None else usage.cache_creation
                ),
                duration_ms=_elapsed(self._clock, started),
                ok=result is not None,
            ),
        )


def metered(
    encode: Encode,
    context: JobContext,
    config: dict[str, object],
    *,
    provider: str,
    tally: Tally | None = None,
    clock: Clock = time.monotonic,
) -> Encode:
    """An encoder that records each batch it embeds as one ledger row.

    The tokens are what the provider reported to ``tally`` for that batch; an
    encoder that reports none (a model loaded in process) leaves them unknown,
    and the time it took is recorded either way.
    """
    name = str(config.get("name") or config["model"])
    upstream = str(config["model"])

    def encoded(texts: list[str]) -> Sequence[Sequence[float]]:
        started = clock()
        ok = False
        try:
            vectors = encode(texts)
            ok = True
            return vectors
        finally:
            record(
                context.database,
                context.job_id,
                Call(
                    model=name,
                    role="embedding",
                    provider=provider,
                    upstream_model=upstream,
                    input_tokens=None if tally is None else tally.take(),
                    output_tokens=None,
                    cache_read_tokens=None,
                    cache_creation_tokens=None,
                    duration_ms=_elapsed(clock, started),
                    ok=ok,
                ),
            )

    return encoded


def record(database: Database, job_id: str | None, call: Call) -> None:
    """Write one call against ``job_id`` and the run (and user) at its root."""
    with database.write() as conn:
        run_id, started_by = _root(conn, job_id)
        conn.execute(
            "INSERT INTO llm_calls (job_id, run_id, started_by, model, role, "
            "provider, upstream_model, input_tokens, output_tokens, "
            "cache_read_tokens, cache_creation_tokens, duration_ms, ok, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                job_id,
                run_id,
                started_by,
                call.model,
                call.role,
                call.provider,
                call.upstream_model,
                call.input_tokens,
                call.output_tokens,
                call.cache_read_tokens,
                call.cache_creation_tokens,
                call.duration_ms,
                int(call.ok),
                datetime.now(UTC).isoformat(),
            ),
        )


def _root(
    conn: sqlite3.Connection, job_id: str | None
) -> tuple[str | None, str | None]:
    """The run a job belongs to — its topmost ancestor — and who started it."""
    if job_id is None:
        return None, None
    row = conn.execute(
        "WITH RECURSIVE up(id, parent_id, started_by) AS ("
        "SELECT id, parent_id, started_by FROM jobs WHERE id = ? "
        "UNION ALL SELECT j.id, j.parent_id, j.started_by FROM jobs j "
        "JOIN up ON j.id = up.parent_id) "
        "SELECT id, started_by FROM up WHERE parent_id IS NULL",
        (job_id,),
    ).fetchone()
    if row is None:
        return job_id, None
    return row["id"], row["started_by"]


def _elapsed(clock: Clock, started: float) -> int:
    return max(0, round((clock() - started) * 1000))
