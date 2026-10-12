"""A composite run tells its watcher each stage as it starts and ends."""

from __future__ import annotations

import pytest

from hrono.jobs.stages import StageFailed, Stages


def test_each_stage_is_reported_as_it_starts_and_as_it_ends() -> None:
    seen: list[dict[str, object]] = []
    run = Stages(clock=lambda: 0.0, report=seen.append)

    run.run("sync", lambda: {"fetched": 1}, over="lear")
    run.run("embed", lambda: None)

    assert [s.get("current") for s in seen] == [
        {"op": "sync", "over": "lear"},
        None,
        {"op": "embed", "over": None},
        None,
    ]
    assert [len(s["stages"]) for s in seen] == [0, 1, 1, 2]  # type: ignore[arg-type]


def test_a_report_that_fails_never_fails_the_run() -> None:
    def broken(_: dict[str, object]) -> None:
        raise RuntimeError("the database is busy")

    run = Stages(report=broken)

    assert run.run("sync", lambda: {"fetched": 1}) == {"fetched": 1}


def test_a_failing_stage_still_raises_with_the_stages_before_it() -> None:
    run = Stages(report=lambda _: None)
    run.run("sync", lambda: None)

    def boom() -> None:
        raise ValueError("no")

    with pytest.raises(StageFailed) as failed:
        run.run("condense", boom)

    assert failed.value.stage == "condense"
    assert len(failed.value.outcome["stages"]) == 1  # type: ignore[arg-type]
