"""The ``hrono profile`` command group over the profile store.

Commands never print or log the token; ``current`` reports only that a token is
set.
"""

from __future__ import annotations

from typing import Annotated

import typer

from hrono.profile.store import Profile, Store, config_path

app = typer.Typer(add_completion=False, help="Manage client profiles.")


def _store() -> Store:
    return Store(config_path())


@app.command("add")
def add(
    name: str,
    server: Annotated[str, typer.Option("--server")],
    token: Annotated[str, typer.Option("--token")],
    default_tree: Annotated[str | None, typer.Option("--default-tree")] = None,
) -> None:
    """Register a profile; the first one added becomes current."""

    _store().add(Profile(name, server, token, default_tree))
    typer.echo(f"Added profile '{name}'.")


@app.command("list")
def list_profiles() -> None:
    """List every profile, marking the current one."""

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


@app.command("use")
def use(name: str) -> None:
    """Switch the current profile."""

    _store().use(name)
    typer.echo(f"Now using profile '{name}'.")


@app.command("current")
def current() -> None:
    """Print the current profile without revealing the token."""

    active = _store().current()
    if active is None:
        typer.echo("No current profile. Set one with 'hrono profile use'.")
        return
    typer.echo(f"{active.name}\t{active.server_url}\t(token set)")


@app.command("rm")
def remove(name: str) -> None:
    """Remove a profile; if it was current, clear the current pointer."""

    cleared = _store().remove(name)
    typer.echo(f"Removed profile '{name}'.")
    if cleared:
        typer.echo("It was the current profile; no profile is current now.")
