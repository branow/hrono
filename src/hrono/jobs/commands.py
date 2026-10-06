"""The ``hrono jobs`` command group (#138): what did my one verb actually do?

`hrono tree sync` runs six stages behind one call, which is only acceptable if
the operator can find out what happened. `jobs get` renders the job's `result`
— the per-stage counts #132 persists — so a run that declined part of its work
says so here instead of nowhere.

Read-only on purpose. Triggering an individual op is a debug door, not a
command (#139).

``get`` and ``watch`` exit non-zero for a job that failed or was canceled, so
a script can gate on them; both used to exit 0 whatever happened, which made
them unusable as anything but scenery.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from hrono.client.http import from_profile

app = typer.Typer(add_completion=False, help="Inspect background jobs.")

_STATUSES = "pending|running|succeeded|failed|canceled"

_JSON = typer.Option("--json", help="Print raw JSON instead of lines.")


@app.command("list")
def list_jobs(
    op: Annotated[
        str | None,
        typer.Option("--op", help="Only jobs of this op (e.g. sync-tree)."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option("--status", help=f"Only this status: {_STATUSES}."),
    ] = None,
    as_json: Annotated[bool, _JSON] = False,
) -> None:
    """List jobs (the newest 500), most useful filtered by op or status."""

    query = [
        f"{key}={value}"
        for key, value in (("op", op), ("status", status))
        if value
    ]
    suffix = f"?{'&'.join(query)}" if query else ""
    rows = from_profile().get(f"/jobs{suffix}")
    if as_json:
        typer.echo(json.dumps(rows, indent=2))
        return
    if not isinstance(rows, list) or not rows:
        typer.echo("no jobs")
        return
    for row in rows:
        shown = str(row.get("op") or "?")
        typer.echo(f"{row.get('id')}  {shown:<12} {row.get('status')}")


@app.command("get")
def get_job(
    job_id: str,
    as_json: Annotated[bool, _JSON] = False,
) -> None:
    """Show one job; exits 1 when it failed or was canceled."""

    job = from_profile().get(f"/jobs/{job_id}")
    if not isinstance(job, dict):
        typer.echo("no such job", err=True)
        raise typer.Exit(1)
    if as_json:
        typer.echo(json.dumps(job, indent=2))
        _gate(str(job.get("status")))
        return
    typer.echo(f"{job.get('id')}  {job.get('op')}  {job.get('status')}")
    progress = job.get("progress")
    if isinstance(progress, dict):  # a parent, answering for its children
        typer.echo(
            f"progress: {progress.get('done')} of {progress.get('total')} "
            f"stages done"
        )
    error = job.get("error")
    if isinstance(error, dict):  # the envelope, as every surface serves it
        typer.echo(f"error: {error.get('code')}: {error.get('message')}")
    cost = job.get("cost")
    if isinstance(cost, dict):
        typer.echo(f"tokens: {cost.get('input')} in, {cost.get('output')} out")
    result = job.get("result")
    if result is None:
        typer.echo("result: none reported")
    else:
        typer.echo("result:")
        typer.echo(json.dumps(result, indent=2))
    _gate(str(job.get("status")))


def _gate(status: str) -> None:
    """Exit 1 on a bad terminal status, so scripts can gate on this command."""
    if status in ("failed", "canceled"):
        raise typer.Exit(1)


@app.command("cancel")
def cancel_job(job_id: str) -> None:
    """Stop a job and its pending children; say what could not be stopped."""

    outcome = from_profile().post(f"/jobs/{job_id}/cancel", {})
    if not isinstance(outcome, dict):
        typer.echo("no such job", err=True)
        raise typer.Exit(1)
    stopped = outcome.get("stopped", 0)
    running = outcome.get("running", 0)
    plural = "job" if stopped == 1 else "jobs"
    typer.echo(f"Stopped {stopped} pending {plural}.")
    if running:
        # the running one was SIGNALED: it halts at its next checkpoint, but
        # the step in flight finishes (#173) — interrupting it mid-write is
        # how a database corrupts.
        stage = "stage was" if running == 1 else "stages were"
        typer.echo(f"{running} {stage} told to stop and will finish its step.")


@app.command("watch")
def watch_job(job_id: str) -> None:
    """Follow a job until it ends; exits 1 when it failed or was canceled."""

    last: dict[str, object] = {}
    for line in from_profile().stream(f"/jobs/{job_id}/events"):
        if not line.startswith("data: "):
            continue  # the event name and the blank separator
        try:
            state = json.loads(line[len("data: ") :])
        except ValueError:
            continue  # one malformed frame must not end the whole watch
        if not isinstance(state, dict):
            continue
        last = state
        progress = state.get("progress")
        shown = f"{state.get('status')}"
        if isinstance(progress, dict):
            shown += f"  {progress.get('done')}/{progress.get('total')}"
        typer.echo(shown)
    error = last.get("error")
    if isinstance(error, dict):
        typer.echo(
            f"error: {error.get('code')}: {error.get('message')}", err=True
        )
    _gate(str(last.get("status")))
