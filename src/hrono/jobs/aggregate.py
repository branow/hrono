"""What a parent job's children add up to (T57.1, #172).

`jobs/model.py` has said since M0 that the parent-only ``partial`` status is
"derived at read time, never stored, so it is absent from ``JobStatus``". This
is that derivation, and it is a pure function over the children's statuses so
it can be tested without a database and cannot drift from what is stored.

Derived rather than stored, deliberately: a stored aggregate is a second source
of truth that is wrong from the moment a child changes until something
remembers to re-aggregate, and nothing in this system is obliged to remember.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from hrono.jobs.model import JobStatus

PARTIAL = "partial"

_TERMINAL = frozenset(
    {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED}
)


@dataclass(frozen=True)
class Rollup:
    """A parent's status and progress, as its children make it."""

    status: str
    done: int
    total: int


def rollup(children: Sequence[str]) -> Rollup | None:
    """The parent's answer, or None when it has no children to answer for.

    None and not a zero Rollup: a job with no children is a LEAF, and a leaf
    answers for itself. Inventing `0 of 0` progress for one would put a
    progress bar on every single-stage job in the system.

    The order of the rules is the whole design:

    - a FAILED child fails the parent even if others are still running. The
      run cannot now succeed, and saying "running" would have an operator wait
      for an outcome that has already been decided.
    - CANCELED outranks running for the same reason, and ranks below failed:
      "it broke" is what a person needs to hear first.
    - PARTIAL is for a parent whose children have all finished EXCEPT some —
      the state the spec named and the one a progress bar is for.
    - SUCCEEDED only when every child did. A parent that reports success over
      an unfinished child is #132's defect with more moving parts.
    """
    if not children:
        return None
    counts = Counter(children)
    done = sum(counts[status] for status in _TERMINAL)
    total = len(children)
    return Rollup(status=_status(counts, done, total), done=done, total=total)


def _status(counts: Counter[str], done: int, total: int) -> str:
    if counts[JobStatus.FAILED]:
        return JobStatus.FAILED
    if counts[JobStatus.CANCELED]:
        return JobStatus.CANCELED
    if done == total:
        return JobStatus.SUCCEEDED
    if counts[JobStatus.SUCCEEDED]:
        return PARTIAL
    if counts[JobStatus.RUNNING]:
        return JobStatus.RUNNING
    return JobStatus.PENDING
