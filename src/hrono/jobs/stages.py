"""A composite op's stages, recorded as they run.

``maintain`` and ``sync-tree`` run a dozen stages in-process, and until this
recorded nothing: a six-minute successful ``maintain`` showed "It reported
nothing", and a failed one showed one error string with no stage and no item.
The most expensive action in the product left no account of itself.

``Stages`` times each stage and keeps what it returned, and the op returns
``outcome()`` as its result. A stage that raises is re-raised as
``StageFailed``, which carries the stages that DID finish — the worker stores
them as the failed job's result — and names the stage and the item it was on.

The item comes from the exception itself: ``pool.mapped`` notes which item a
failed call was for (``ITEM`` note), so a condense that died on one section
says which section rather than "condense failed".
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

ITEM = "item: "


class StageFailed(Exception):
    """A stage of a composite op raised; ``cause`` is what it raised."""

    def __init__(
        self,
        stage: str,
        item: str | None,
        cause: BaseException,
        outcome: Mapping[str, object],
    ) -> None:
        super().__init__(str(cause))
        self.stage = stage
        self.item = item
        self.cause = cause
        self.outcome = outcome


@dataclass(frozen=True)
class Done:
    """One finished stage: which, over what, how long, what it returned."""

    op: str
    over: str | None
    seconds: float
    result: Mapping[str, object] | None

    def view(self) -> dict[str, object]:
        return {
            "op": self.op,
            "over": self.over,
            "seconds": round(self.seconds, 2),
            "result": None if self.result is None else dict(self.result),
        }


class Stages:
    """The stages one run of a composite op has finished, in order.

    Mutable by nature — it is the run's log as it happens — and owned by the
    single call that creates it.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._done: list[Done] = []

    def run[Made](
        self, op: str, call: Callable[[], Made], *, over: str | None = None
    ) -> Made:
        """Run one stage; record it, or raise ``StageFailed`` naming it."""
        started = self._clock()
        try:
            made = call()
        except StageFailed:
            raise
        except Exception as exc:
            raise StageFailed(
                op, noted_item(exc) or over, exc, self.outcome()
            ) from exc
        result = made if isinstance(made, Mapping) else None
        self._done.append(Done(op, over, self._clock() - started, result))
        return made

    def outcome(
        self, extra: Mapping[str, object] | None = None
    ) -> dict[str, object]:
        """The result to store: what the op reports, and every stage."""
        return {
            **(dict(extra) if extra else {}),
            "stages": [done.view() for done in self._done],
        }


def note_item(exc: BaseException, item: str) -> None:
    """Say on a failure which item it was for (the first note wins)."""
    if noted_item(exc) is None:
        exc.add_note(ITEM + item)


def noted_item(exc: BaseException) -> str | None:
    for note in getattr(exc, "__notes__", ()):
        if isinstance(note, str) and note.startswith(ITEM):
            return note.removeprefix(ITEM)
    return None
