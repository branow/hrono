"""What a turn is shown as: a list of steps, appended while it runs.

The page reads the list from where it last stopped, so a step is never
changed after it is added. A turn ends with one ``done`` or ``failed`` step.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Literal

Kind = Literal[
    "asked",  # the question as typed
    "recall",  # what the hook attached, or why nothing was
    "prompt",  # the text the model received
    "say",  # what the model said before using a tool
    "tool",  # a tool call and what it returned
    "answer",  # the model's final text
    "done",  # the turn finished; usage beside it
    "failed",  # the turn stopped on an error
]
FINAL: frozenset[Kind] = frozenset({"done", "failed"})


@dataclass(frozen=True)
class Step:
    """One thing that happened in a turn, with what the page shows of it."""

    kind: Kind
    data: dict[str, object] = field(default_factory=dict)


class Steps:
    """A conversation's steps, safe to append from the turn's thread."""

    def __init__(self) -> None:
        self._items: list[Step] = []
        self._lock = threading.Lock()

    def add(self, kind: Kind, **data: object) -> None:
        with self._lock:
            self._items.append(Step(kind, data))

    def since(self, after: int) -> list[Step]:
        """The steps after the first ``after`` of them."""
        with self._lock:
            return self._items[after:]

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
