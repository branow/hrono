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

import typer

from hrono.client.http import from_profile

app = typer.Typer(add_completion=False, help="Inspect background jobs.")


@app.command("list")
def list_jobs(
    op: str | None = None,
    status: str | None = None,
) -> None:
    """List jobs, most useful filtered by op or status."""

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
        typer.echo(f"{row.get('id')}  {row.get('op'):<12} {row.get('status')}")


@app.command("get")
def get_job(job_id: str) -> None:
    """Show one job, including what it reported doing."""

    job = from_profile().get(f"/jobs/{job_id}")
    if not isinstance(job, dict):
        typer.echo("no such job", err=True)
        raise typer.Exit(1)
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
    result = job.get("result")
    if result is None:
        typer.echo("result: none reported")
        return
    typer.echo("result:")
    typer.echo(json.dumps(result, indent=2))


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
        # the honest half: a running handler cannot be interrupted without
        # risking a half-written transaction, so it finishes (#173)
        stage = "stage is" if running == 1 else "stages are"
        typer.echo(f"{running} {stage} already running and will finish.")


@app.command("watch")
def watch_job(job_id: str) -> None:
    """Follow a job's progress until it ends (SSE)."""

    for line in from_profile().stream(f"/jobs/{job_id}/events"):
        if not line.startswith("data: "):
            continue  # the event name and the blank separator
        state = json.loads(line[len("data: ") :])
        progress = state.get("progress")
        shown = f"{state.get('status')}"
        if isinstance(progress, dict):
            shown += f"  {progress.get('done')}/{progress.get('total')}"
        typer.echo(shown)
