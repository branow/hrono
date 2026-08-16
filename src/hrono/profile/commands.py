"""The ``hrono profile`` command group over the profile store.

Commands never print or log the token; ``current`` reports only that a token is
set.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

import typer

from hrono.errors import AppError, cli_message
from hrono.profile.store import Profile, Store, config_path

app = typer.Typer(add_completion=False, help="Manage client profiles.")


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
    """Register a profile; the first one added becomes current."""

    def action() -> None:
        _store().add(Profile(name, server, token, default_tree))
        typer.echo(f"Added profile '{name}'.")

    _run(action)


@app.command("list")
def list_profiles() -> None:
    """List every profile, marking the current one."""

    def action() -> None:
        store = _store()
        profiles = store.profiles()
        if not profiles:
            typer.echo("No profiles yet. Add one with 'hrono profile add'.")
            return
        active = store.current()
        current_name = active.name if active is not None else None
        for profile in profiles:
            marker = "*" if profile.name == current_name else " "
            typer.echo(f"{marker} {profile.name}\t{profile.server_url}")

    _run(action)


@app.command("use")
def use(name: str) -> None:
    """Switch the current profile."""

    def action() -> None:
        _store().use(name)
        typer.echo(f"Now using profile '{name}'.")

    _run(action)


@app.command("current")
def current() -> None:
    """Print the current profile without revealing the token."""

    def action() -> None:
        active = _store().current()
        if active is None:
            typer.echo("No current profile. Set one with 'hrono profile use'.")
            return
        typer.echo(f"{active.name}\t{active.server_url}\t(token set)")

    _run(action)


@app.command("rm")
def remove(name: str) -> None:
    """Remove a profile; if it was current, clear the current pointer."""

    def action() -> None:
        cleared = _store().remove(name)
        typer.echo(f"Removed profile '{name}'.")
        if cleared:
            typer.echo("It was the current profile; no profile is current now.")

    _run(action)
