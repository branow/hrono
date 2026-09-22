"""The ``hrono tree`` command group — the CLI face of the tree routes.

``hrono tree sync <name>`` is THE operator verb: one command brings an existing
tree up to date after its sources changed. ``hrono tree maintain <name>`` is the
COLD build, for a tree that does not exist yet — they have very different costs
and are deliberately separate commands.

``hrono tree maintain <name>`` POSTs to ``/trees/<name>/maintain`` through the
current profile's client and prints the job id to track. (The spec writes it
kubectl-style as ``tree <name> maintain``; Typer groups put the subcommand
first, and the HTTP endpoint is the canonical interface.)
``hrono tree pending <name>`` reads the incubator pool so a chunk waiting
outside the tree is visible from the CLI instead of silently absent.
``hrono tree export <name> -o <dir>`` materialises the rendered map under
``<dir>``: every payload path is forced relative before the traversal guard
runs, so a server path with a leading slash lands in the folder instead of
rerooting the export (#096), and a refused entry costs only itself.
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


@app.command("sync")
def sync(name: str) -> None:
    """Bring a tree up to date after its sources changed; prints the job id."""

    def action() -> None:
        result = from_profile().post(f"/trees/{name}/sync", {})
        job_id = result.get("job_id") if isinstance(result, dict) else None
        typer.echo(f"Started sync job {job_id} for tree '{name}'.")

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
        written, refused = _materialize(out, files)
        plural = "file" if written == 1 else "files"
        typer.echo(f"Wrote {written} {plural} to {out}.")
        if refused:
            listed = ", ".join(repr(path) for path in refused[:3])
            raise UnsafePath(
                f"refused {len(refused)} of {len(files)} files that would "
                f"write outside {out}: {listed}"
            )

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


def _materialize(
    out: Path, files: list[dict[str, str]]
) -> tuple[int, tuple[str, ...]]:
    """Write every entry under ``out``; return (written, refused paths).

    A leading slash is NORMALISED rather than obeyed: ``out / "/a.md"`` is
    ``/a.md`` to pathlib, which would reroot the whole export out of the output
    folder (#096, F19). An entry is written only if it names a file strictly
    under ``out``: one that escapes, or that lands ON ``out`` itself ("/", ".",
    "" — a directory, not a file), is refused and counted instead. One bad
    entry costs its own file, not the other ninety-three.
    """
    out.mkdir(parents=True, exist_ok=True)
    base = out.resolve()
    written = 0
    refused: list[str] = []
    for entry in files:
        target = (out / entry["path"].lstrip("/")).resolve()
        if target == base or base not in target.parents:
            refused.append(entry["path"])
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(entry.get("content", ""), encoding="utf-8")
        written += 1
    return written, tuple(refused)
