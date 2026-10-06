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
    server: Annotated[
        str,
        typer.Option(
            "--server", help="Server URL, e.g. http://127.0.0.1:8080."
        ),
    ],
    token: Annotated[
        str,
        typer.Option(
            "--token",
            help=(
                "API token. Omit it to be prompted (keeps it out of shell "
                "history), or set $HRONO_TOKEN."
            ),
            envvar="HRONO_TOKEN",
            prompt="Token",
            hide_input=True,
        ),
    ],
    default_tree: Annotated[
        str | None,
        typer.Option(
            "--default-tree",
            help="The tree 'hrono recall' uses when none is named.",
        ),
    ] = None,
) -> None:
    """Register a profile; the first one added becomes current."""

    _store().add(Profile(name, server, token, default_tree))
    typer.echo(f"Added profile '{name}'.")


@app.command("set-token")
def set_token(
    name: str,
    token: Annotated[
        str,
        typer.Option(
            "--token",
            help=(
                "The new API token. Omit it to be prompted, or set "
                "$HRONO_TOKEN."
            ),
            envvar="HRONO_TOKEN",
            prompt="Token",
            hide_input=True,
        ),
    ],
) -> None:
    """Replace a profile's token — the step after 'hrono admin reset-token'."""

    _store().set_token(name, token)
    typer.echo(f"Updated the token of profile '{name}'.")


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
def remove(
    name: str,
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip the confirmation prompt."),
    ] = False,
) -> None:
    """Remove a profile; if it was current, clear the current pointer."""

    if not force and not typer.confirm(f"Remove profile '{name}'?"):
        typer.echo("Aborted; nothing was changed.", err=True)
        raise typer.Exit(1)
    cleared = _store().remove(name)
    typer.echo(f"Removed profile '{name}'.")
    if cleared:
        typer.echo("It was the current profile; no profile is current now.")
