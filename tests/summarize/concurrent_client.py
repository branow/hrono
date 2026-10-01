"""Fake ``Completion`` clients that can SEE whether calls overlap.

A test that only checks an op's results passes against the serial loop these
replace, so neither of these is a recorder: each makes the parallelism itself
the thing that has to happen.

``Paired`` completes only in twos — it parks on a two-party barrier — so a
caller that makes one call at a time hits the barrier timeout and the op raises
``BrokenBarrierError``. ``Overlap`` lets every call through but holds each one
briefly and records the high-water mark, which is how a test asserts the
ABSENCE of concurrency: ``peak`` cannot exceed 1 unless two calls really were
in flight.
"""

from __future__ import annotations

import threading
import time

from hrono.llm.client import CompletionRequest, CompletionResult, Usage

TEXT = "The brief body describes what this topic contains."
USAGE = (10, 3)


class Paired:
    """Answers only while a second call is inside ``complete`` as well."""

    def __init__(self, text: str = TEXT, timeout: float = 3.0) -> None:
        self._gate = threading.Barrier(2, timeout=timeout)
        self._guard = threading.Lock()
        self._inside = 0
        self._text = text
        self.calls = 0
        self.peak = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        with self._guard:
            self.calls += 1
            self._inside += 1
            self.peak = max(self.peak, self._inside)
        try:
            self._gate.wait()
        finally:
            with self._guard:
                self._inside -= 1
        return CompletionResult(self._text, Usage(*USAGE))


class Overlap:
    """Answers every call, holding each long enough for another to arrive."""

    def __init__(self, text: str = TEXT, hold: float = 0.05) -> None:
        self._guard = threading.Lock()
        self._inside = 0
        self._hold = hold
        self._text = text
        self.calls = 0
        self.peak = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        with self._guard:
            self.calls += 1
            self._inside += 1
            self.peak = max(self.peak, self._inside)
        time.sleep(self._hold)
        with self._guard:
            self._inside -= 1
        return CompletionResult(self._text, Usage(*USAGE))
