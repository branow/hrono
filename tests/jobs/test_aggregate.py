"""What a parent job's children add up to.

A pure function over statuses, so the rules can be stated as a table rather
than constructed a database at a time. The HTTP half is in
`tests/server/test_job_children.py`.
"""

from __future__ import annotations

import pytest

from hrono.jobs.aggregate import PARTIAL, Rollup, rollup
from hrono.jobs.model import JobStatus

P = JobStatus.PENDING
R = JobStatus.RUNNING
S = JobStatus.SUCCEEDED
F = JobStatus.FAILED
C = JobStatus.CANCELED


@pytest.mark.parametrize(
    ("children", "expected"),
    [
        ([S, S, S], JobStatus.SUCCEEDED),
        ([S, S, P], PARTIAL),
        ([S, R, P], PARTIAL),
        ([R, P], JobStatus.RUNNING),
        ([P, P], JobStatus.PENDING),
        ([S, F, P], JobStatus.FAILED),
        ([R, F], JobStatus.FAILED),
        ([S, C, P], JobStatus.CANCELED),
        ([F, C], JobStatus.FAILED),
        ([C, C], JobStatus.CANCELED),
    ],
)
def test_the_rules_as_a_table(children: list[str], expected: str) -> None:
    result = rollup(children)
    assert result is not None
    assert result.status == expected


def test_progress_counts_the_finished_children() -> None:
    assert rollup([S, F, C, R, P]) == Rollup(
        status=JobStatus.FAILED, done=3, total=5
    )
    # a failure outranks work still running: the run cannot now succeed, and
    # "running" would have an operator wait for an outcome already decided.
    assert rollup([F, R, P]) == Rollup(status=JobStatus.FAILED, done=1, total=3)


def test_a_job_with_no_children_is_a_leaf_and_answers_for_itself() -> None:
    # None, not a zero Rollup: inventing `0 of 0` would put a progress bar on
    # every single-stage job in the system.
    assert rollup([]) is None
