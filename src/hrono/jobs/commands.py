"""The ``hrono jobs`` command group (#138): what did my one verb actually do?

`hrono tree sync` runs six stages behind one call, which is only acceptable if
the operator can find out what happened. `jobs get` renders the job's `result`
— the per-stage counts #132 persists — so a run that declined part of its work
says so here instead of nowhere.

Read-only on purpose. Triggering an individual op is a debug door, not a
command (#139).
"""

from __future__ import annotations

import json
from collections.abc import Callable

import typer

from hrono.client.http import ClientError, from_profile, message

app = typer.Typer(add_completion=False, help="Inspect background jobs.")


def _run(action: Callable[[], None]) -> None:
    try:
        action()
    except ClientError as exc:
        typer.echo(message(exc), err=True)
        raise typer.Exit(1) from exc


@app.command("list")
def list_jobs(
    op: str | None = None,
    status: str | None = None,
) -> None:
    """List jobs, most useful filtered by op or status."""

    def action() -> None:
        query = [
            f"{key}={value}"
            for key, value in (("op", op), ("status", status))
            if value
        ]
        suffix = f"?{'&'.join(query)}" if query else ""
        rows = from_profile().get(f"/jobs{suffix}")
        if not isinstance(rows, list) or not rows:
            typer.echo("no jobs")
            return
        for row in rows:
            typer.echo(
                f"{row.get('id')}  {row.get('op'):<12} {row.get('status')}"
            )

    _run(action)


@app.command("get")
def get_job(job_id: str) -> None:
    """Show one job, including what it reported doing."""

    def action() -> None:
        job = from_profile().get(f"/jobs/{job_id}")
        if not isinstance(job, dict):
            typer.echo("no such job", err=True)
            raise typer.Exit(1)
        typer.echo(f"{job.get('id')}  {job.get('op')}  {job.get('status')}")
        if job.get("error"):
            typer.echo(f"error: {job['error']}")
        result = job.get("result")
        if result is None:
            typer.echo("result: none reported")
            return
        typer.echo("result:")
        typer.echo(json.dumps(result, indent=2))

    _run(action)
