"""The ``hrono tree`` command group — the CLI face of the tree routes.

``hrono tree maintain <name>`` POSTs to ``/trees/<name>/maintain`` through the
current profile's client and prints the job id to track. (The spec writes it
kubectl-style as ``tree <name> maintain``; Typer groups put the subcommand
first, and the HTTP endpoint is the canonical interface.)
``hrono tree pending <name>`` reads the incubator pool so a chunk waiting
outside the tree is visible from the CLI instead of silently absent.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from hrono.client.http import ClientError, from_profile, message

app = typer.Typer(add_completion=False, help="Build and maintain trees.")


class UnsafePath(Exception):
    """A payload path tried to escape the output directory."""


def _run(action: Callable[[], None]) -> None:
    try:
        action()
    except ClientError as exc:
        typer.echo(message(exc), err=True)
        raise typer.Exit(1) from exc
    except UnsafePath as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc


@app.command("maintain")
def maintain(name: str) -> None:
    """Kick a full build-to-root maintain for a tree; prints the job id."""

    def action() -> None:
        result = from_profile().post(f"/trees/{name}/maintain", {})
        job_id = result.get("job_id") if isinstance(result, dict) else None
        typer.echo(f"Started maintain job {job_id} for tree '{name}'.")

    _run(action)


@app.command("export")
def export(
    name: str,
    out: Annotated[Path, typer.Option("-o", "--out")],
    levels: Annotated[int, typer.Option("--levels")] = 4,
) -> None:
    """Materialize a tree's rendered map into a folder under ``--out``."""

    def action() -> None:
        result = from_profile().get(f"/trees/{name}/export?levels={levels}")
        files = result.get("files", []) if isinstance(result, dict) else []
        written = _materialize(out, files)
        typer.echo(f"Wrote {written} files to {out}.")

    _run(action)


@app.command("pending")
def pending(name: str) -> None:
    """List the tree's incubator pool — chunks parked in no node yet."""

    def action() -> None:
        result = from_profile().get(f"/trees/{name}/pending")
        pool = result.get("pending", []) if isinstance(result, dict) else []
        for entry in pool:
            typer.echo(f"{entry['path']} (batch {entry['batch']})")
        chunks = "chunk" if len(pool) == 1 else "chunks"
        typer.echo(f"{len(pool)} pending {chunks} in tree '{name}'.")

    _run(action)


def _materialize(out: Path, files: list[dict[str, str]]) -> int:
    out.mkdir(parents=True, exist_ok=True)
    base = out.resolve()
    written = 0
    for entry in files:
        target = (out / entry["path"]).resolve()
        if base != target and base not in target.parents:
            raise UnsafePath(
                f"refused to write outside {out}: {entry['path']!r}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(entry.get("content", ""), encoding="utf-8")
        written += 1
    return written
