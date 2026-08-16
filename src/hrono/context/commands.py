"""The ``hrono context`` command group over the context store.

Commands never print or log the token; ``current`` reports only that a token is
set.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

import typer

from hrono.context.store import Context, Store, config_path
from hrono.errors import AppError, cli_message

app = typer.Typer(add_completion=False, help="Manage client contexts.")


def _store() -> Store:
    return Store(config_path())


def _run(action: Callable[[], None]) -> None:
    """Run a command body, rendering any domain error to a clean CLI line."""
    try:
        action()
    except AppError as exc:
        typer.echo(cli_message(exc), err=True)
        raise typer.Exit(1) from exc


@app.command("add")
def add(
    name: str,
    server: Annotated[str, typer.Option("--server")],
    token: Annotated[str, typer.Option("--token")],
    default_tree: Annotated[str | None, typer.Option("--default-tree")] = None,
) -> None:
    """Register a context; the first one added becomes current."""

    def action() -> None:
        _store().add(Context(name, server, token, default_tree))
        typer.echo(f"Added context '{name}'.")

    _run(action)


@app.command("list")
def list_contexts() -> None:
    """List every context, marking the current one."""

    def action() -> None:
        store = _store()
        contexts = store.contexts()
        if not contexts:
            typer.echo("No contexts yet. Add one with 'hrono context add'.")
            return
        active = store.current()
        current_name = active.name if active is not None else None
        for context in contexts:
            marker = "*" if context.name == current_name else " "
            typer.echo(f"{marker} {context.name}\t{context.server_url}")

    _run(action)


@app.command("use")
def use(name: str) -> None:
    """Switch the current context."""

    def action() -> None:
        _store().use(name)
        typer.echo(f"Now using context '{name}'.")

    _run(action)


@app.command("current")
def current() -> None:
    """Print the current context without revealing the token."""

    def action() -> None:
        active = _store().current()
        if active is None:
            typer.echo("No current context. Set one with 'hrono context use'.")
            return
        typer.echo(f"{active.name}\t{active.server_url}\t(token set)")

    _run(action)


@app.command("rm")
def remove(name: str) -> None:
    """Remove a context; if it was current, clear the current pointer."""

    def action() -> None:
        cleared = _store().remove(name)
        typer.echo(f"Removed context '{name}'.")
        if cleared:
            typer.echo("It was the current context; no context is current now.")

    _run(action)
