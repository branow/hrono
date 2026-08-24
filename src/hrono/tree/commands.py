"""The ``hrono tree`` command group — the CLI face of the tree routes.

``hrono tree maintain <name>`` POSTs to ``/trees/<name>/maintain`` through the
current profile's client and prints the job id to track. (The spec writes it
kubectl-style as ``tree <name> maintain``; Typer groups put the subcommand
first, and the HTTP endpoint is the canonical interface.)
"""

from __future__ import annotations

from collections.abc import Callable

import typer

from hrono.client.http import ClientError, from_profile, message

app = typer.Typer(add_completion=False, help="Build and maintain trees.")


def _run(action: Callable[[], None]) -> None:
    try:
        action()
    except ClientError as exc:
        typer.echo(message(exc), err=True)
        raise typer.Exit(1) from exc


@app.command("maintain")
def maintain(name: str) -> None:
    """Kick a full build-to-root maintain for a tree; prints the job id."""

    def action() -> None:
        result = from_profile().post(f"/trees/{name}/maintain", {})
        job_id = result.get("job_id") if isinstance(result, dict) else None
        typer.echo(f"Started maintain job {job_id} for tree '{name}'.")

    _run(action)
