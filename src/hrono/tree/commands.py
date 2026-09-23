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

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from hrono.client.http import from_profile

_WHY = {
    "escapes": "write outside",
    "collides": "collide with a path already written under",
}

app = typer.Typer(add_completion=False, help="Build and maintain trees.")


class UnsafePath(Exception):
    """A payload path tried to escape the output directory."""


@app.command("maintain")
def maintain(name: str) -> None:
    """Kick a full build-to-root maintain for a tree; prints the job id."""

    result = from_profile().post(f"/trees/{name}/maintain", {})
    job_id = result.get("job_id") if isinstance(result, dict) else None
    typer.echo(f"Started maintain job {job_id} for tree '{name}'.")


@app.command("sync")
def sync(name: str) -> None:
    """Bring a tree up to date after its sources changed; prints the job id."""

    result = from_profile().post(f"/trees/{name}/sync", {})
    job_id = result.get("job_id") if isinstance(result, dict) else None
    typer.echo(f"Started sync job {job_id} for tree '{name}'.")


@app.command("export")
def export(
    name: str,
    out: Annotated[Path, typer.Option("-o", "--out")],
    levels: Annotated[int, typer.Option("--levels")] = 4,
) -> None:
    """Materialize a tree's rendered map into a folder under ``--out``."""

    result = from_profile().get(f"/trees/{name}/export?levels={levels}")
    files = result.get("files", []) if isinstance(result, dict) else []
    written, refused = _materialize(out, files)
    plural = "file" if written == 1 else "files"
    typer.echo(f"Wrote {written} {plural} to {out}.")
    if refused:
        raise UnsafePath(_refusal(out, len(files), refused))


@app.command("pending")
def pending(name: str) -> None:
    """List the tree's incubator pool — chunks parked in no node yet."""

    result = from_profile().get(f"/trees/{name}/pending")
    pool = result.get("pending", []) if isinstance(result, dict) else []
    for entry in pool:
        typer.echo(f"{entry['path']} (batch {entry['batch']})")
    chunks = "chunk" if len(pool) == 1 else "chunks"
    typer.echo(f"{len(pool)} pending {chunks} in tree '{name}'.")


@dataclass(frozen=True)
class Refusal:
    """One entry that was not written, and which KIND of problem it was."""

    path: str
    reason: str  # "escapes" | "collides"


def _refusal(out: Path, total: int, refused: Sequence[Refusal]) -> str:
    """One line that says how many were refused and WHY (#117).

    The message used to say every refusal "would write outside" the folder,
    which is untrue of half of them: a degenerate path ("/", ".", "") writes
    ONTO the folder, and a directory collision writes inside it. A user who saw
    that line was told something false about their own data.
    """
    kinds: dict[str, list[str]] = {}
    for item in refused:
        kinds.setdefault(item.reason, []).append(item.path)
    parts = [
        f"{len(paths)} that would {_WHY[reason]} "
        f"({', '.join(repr(p) for p in paths[:3])})"
        for reason, paths in sorted(kinds.items())
    ]
    return f"refused {len(refused)} of {total} files: " + "; ".join(parts)


def _materialize(
    out: Path, files: list[dict[str, str]]
) -> tuple[int, tuple[Refusal, ...]]:
    """Write every entry under ``out``; return (written, refusals).

    A leading slash is NORMALISED rather than obeyed: ``out / "/a.md"`` is
    ``/a.md`` to pathlib, which would reroot the whole export out of the output
    folder (#096, F19). An entry is written only if it names a file strictly
    under ``out``: one that escapes, or that lands ON ``out`` itself ("/", ".",
    "" — a directory, not a file), is refused and counted instead. One bad
    entry costs its own file, not the other ninety-three.

    The WRITE is guarded the same way (#117): a payload whose entries collide on
    disk — ``alpha-1/brief.md`` and then ``alpha-1`` — raises ``OSError`` from
    the ``mkdir`` or the write, and an unguarded loop would lose every entry
    after it AND skip the report entirely, which is the same shape the path
    guard above removed. Unreachable from hrono's own renderer (every key it
    emits ends in ``.md``, and a node directory can never equal a section file
    name), so this is robustness against a hostile or buggy server and against
    the filesystem itself.
    """
    out.mkdir(parents=True, exist_ok=True)
    base = out.resolve()
    written = 0
    refused: list[Refusal] = []
    for entry in files:
        target = (out / entry["path"].lstrip("/")).resolve()
        if target == base or base not in target.parents:
            refused.append(Refusal(entry["path"], "escapes"))
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(entry.get("content", ""), encoding="utf-8")
        except OSError:
            # a payload naming a path that collides with one already written
            # (`alpha-1/brief.md` then `alpha-1`) costs its own file, like any
            # other bad entry — not the ninety-three after it (#117).
            refused.append(Refusal(entry["path"], "collides"))
            continue
        written += 1
    return written, tuple(refused)
