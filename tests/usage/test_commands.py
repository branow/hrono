"""`hrono usage` prints a table a person reads without API docs."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from hrono.cli import app
from hrono.db.database import Database
from hrono.jobs.ops import JobContext
from hrono.jobs.worker import enqueue
from hrono.llm.client import CompletionRequest, Usage
from hrono.llm.ledger import Ledgered
from hrono.usage.commands import render
from hrono.usage.rollup import usage
from tests.test_cli_surface import FakeClient, _patch
from tests.usage.test_rollup import Reporting

runner = CliRunner()


def _served(tmp_path: Path, by: str) -> dict[str, object]:
    """What ``GET /usage`` answers over a ledger the real writer filled."""
    database = Database.at(tmp_path / "hrono.db")
    run_id = enqueue(database, "sync-tree", {}, started_by="ana")
    calls = (
        ("claude-code", Usage(9, 156, 11410, 3294, "claude-haiku-4-5-1")),
        ("anthropic", Usage(1000, 200, model="claude-sonnet-5")),
        ("anthropic", Usage(5, 5, model="mystery-1")),
    )
    for provider, spent in calls:
        Ledgered(
            Reporting(spent),
            JobContext(database, job_id=run_id),
            role="brief",
            provider=provider,
        ).complete(
            CompletionRequest(
                model={"name": f"m-{provider}", "model": "x"},
                system="",
                content="",
            )
        )
    with database.connect() as conn:
        groups = usage(conn, by)
    database.close()
    return {"by": by, "groups": groups}


def test_usage_by_model_is_a_readable_table(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = _patch(
        monkeypatch,
        "hrono.usage.commands",
        FakeClient(_served(tmp_path, "model")),
    )

    result = runner.invoke(
        app, ["usage", "--by", "model", "--since", "2026-10-01"]
    )

    assert result.exit_code == 0
    assert client.calls == [("GET", "/usage?by=model&since=2026-10-01", None)]
    lines = result.stdout.splitlines()
    assert lines[0].split()[:3] == ["MODEL", "CALLS", "FAILED"]
    assert "MODEL-TIME" in lines[0]
    claude_code = next(
        line for line in lines if line.startswith("m-claude-code")
    )
    anthropic = next(line for line in lines if line.startswith("m-anthropic"))
    # the subscription call is an estimate in its own column, never spend
    assert claude_code.split()[-2:] == ["-", "$0.0060"]
    assert anthropic.split()[-2:] == ["unknown", "-"]
    assert "estimate, not money spent" in result.stdout
    assert "no price for mystery-1" in result.stdout


def test_usage_by_run_names_the_op_and_who_started_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch(
        monkeypatch,
        "hrono.usage.commands",
        FakeClient(_served(tmp_path, "run")),
    )

    result = runner.invoke(app, ["usage", "--by", "run"])

    assert result.exit_code == 0
    assert "sync-tree by ana" in result.stdout


def test_usage_with_nothing_recorded_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, "hrono.usage.commands", FakeClient({"groups": []}))

    result = runner.invoke(app, ["usage"])

    assert result.exit_code == 0
    assert "no model calls recorded" in result.stdout


@pytest.mark.parametrize(
    ("seconds", "shown"),
    [
        pytest.param(3.84, "3.8s", id="seconds"),
        pytest.param(750.0, "12.5m", id="minutes"),
        pytest.param(5472.0, "1.52h", id="hours"),
    ],
)
def test_model_time_reads_in_the_unit_a_person_uses(
    seconds: float, shown: str
) -> None:
    group = {"key": "m", "model_seconds": seconds, "cost": {}}

    [_, row, *_] = render("model", [group])

    assert row.split()[7] == shown
