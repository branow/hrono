"""The ``hrono context`` command group over the context store.

Commands never print or log the token; ``current`` reports only that a token is
set.
"""

from __future__ import annotations

from typing import Annotated

import typer

from hrono.context.store import (
    Context,
    DuplicateContext,
    Store,
    UnknownContext,
    config_path,
)

app = typer.Typer(add_completion=False, help="Manage client contexts.")


def _store() -> Store:
    return Store(config_path())


@app.command("add")
def add(
    name: str,
    server: Annotated[str, typer.Option("--server")],
    token: Annotated[str, typer.Option("--token")],
    default_tree: Annotated[str | None, typer.Option("--default-tree")] = None,
) -> None:
    """Register a context; the first one added becomes current."""
    try:
        _store().add(Context(name, server, token, default_tree))
    except DuplicateContext as exc:
        typer.echo(f"Context '{name}' already exists.", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Added context '{name}'.")


@app.command("list")
def list_contexts() -> None:
    """List every context, marking the current one."""
    store = _store()
    contexts = store.contexts()
    if not contexts:
        typer.echo("No contexts yet. Add one with 'hrono context add'.")
        return
    current = store.current()
    current_name = current.name if current is not None else None
    for context in contexts:
        marker = "*" if context.name == current_name else " "
        typer.echo(f"{marker} {context.name}\t{context.server_url}")


@app.command("use")
def use(name: str) -> None:
    """Switch the current context."""
    try:
        _store().use(name)
    except UnknownContext as exc:
        typer.echo(f"Unknown context '{name}'.", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Now using context '{name}'.")


@app.command("current")
def current() -> None:
    """Print the current context without revealing the token."""
    active = _store().current()
    if active is None:
        typer.echo("No current context. Set one with 'hrono context use'.")
        return
    typer.echo(f"{active.name}\t{active.server_url}\t(token set)")


@app.command("rm")
def remove(name: str) -> None:
    """Remove a context; if it was current, clear the current pointer."""
    try:
        cleared = _store().remove(name)
    except UnknownContext as exc:
        typer.echo(f"Unknown context '{name}'.", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Removed context '{name}'.")
    if cleared:
        typer.echo("It was the current context; no context is current now.")
