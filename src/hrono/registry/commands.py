"""The ``hrono sources|connections|models|prompts`` command groups (#138).

One group per registry collection, all built from the SAME factory: a
collection is only a name here, exactly as it is only a descriptor on the
server. Registering a source used to mean hand-written curl, which is not a
product surface — it is the absence of one.

``set`` reads its config as JSON from a file or stdin and PUTs it, so a config
is declarative: say what it IS and get that, whether or not it was there before
(#138's PUT-creates half). ``rm`` deletes, except for a seeded default, which
the server resets rather than removes.

Secrets are never printed: what comes back from the server is already masked,
and nothing here un-masks it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from hrono.client.http import from_profile


def _read(source: Path | None) -> dict[str, object]:
    """The config to write: a JSON file, or stdin when no file is given."""
    text = source.read_text() if source is not None else sys.stdin.read()
    body = json.loads(text)
    if not isinstance(body, dict):
        raise TypeError("config must be a JSON object")
    return body


def build_app(collection: str) -> typer.Typer:
    """The command group for one registry collection."""
    group = typer.Typer(
        add_completion=False, help=f"Manage {collection} configuration."
    )

    @group.command("list")
    def list_items() -> None:
        """List every configured item in this collection."""

        rows = from_profile().get(f"/{collection}")
        names = (
            [row.get("name") for row in rows] if isinstance(rows, list) else []
        )
        typer.echo("\n".join(str(name) for name in names) or f"no {collection}")

    @group.command("get")
    def get_item(name: str) -> None:
        """Print one item's configuration, secrets masked."""

        item = from_profile().get(f"/{collection}/{name}")
        typer.echo(json.dumps(item, indent=2))

    @group.command("set")
    def set_item(
        name: str,
        file: Annotated[
            Path | None,
            typer.Option("-f", "--file", help="JSON config file, or stdin."),
        ] = None,
    ) -> None:
        """Create or replace an item from a JSON config (file or stdin)."""

        body = _read(file)
        body.setdefault("name", name)
        from_profile().put(f"/{collection}/{name}", body)
        typer.echo(f"Wrote {collection}/{name}.")

    @group.command("rm")
    def remove(name: str) -> None:
        """Delete an item; a seeded default is reset rather than removed."""

        result = from_profile().delete(f"/{collection}/{name}")
        reset = isinstance(result, dict) and "reset" in result
        verb = "Reset" if reset else "Deleted"
        typer.echo(f"{verb} {collection}/{name}.")

    return group
