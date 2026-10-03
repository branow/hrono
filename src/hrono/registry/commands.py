"""The ``hrono sources|connections|models|prompts`` command groups (#138).

One group per registry collection, all built from the SAME factory: a
collection is only a name here, exactly as it is only a descriptor on the
server. Registering a source used to mean hand-written curl, which is not a
product surface — it is the absence of one.

``set`` reads its config as JSON from a file or stdin and PUTs it, so a config
is declarative: say what it IS and get that, whether or not it was there before
(#138's PUT-creates half), with a budget long enough for the validation the
server runs first, and a timeout that names the command which shows whether the
write landed. ``rm`` deletes, except for a seeded default, which the server
resets rather than removes.

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

# ``set`` is not a CRUD write: the server validates what it is given before
# storing it — a connection against its provider, a local embedding model by
# LOADING ITS WEIGHTS (13.3s cold where #168 measured it, more on a slower disk
# or a larger model). The client's 10s default was chosen for reads and fell
# under that, so a write that landed reported a timeout (#199). The same
# budget recall's cold path has, for the same cost.
WRITE_TIMEOUT = 120.0


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
        from_profile().put(
            f"/{collection}/{name}",
            body,
            timeout=WRITE_TIMEOUT,
            check=f"hrono {collection} get {name}",
        )
        typer.echo(f"Wrote {collection}/{name}.")

    @group.command("rm")
    def remove(name: str) -> None:
        """Delete an item; a seeded default is reset rather than removed."""

        result = from_profile().delete(f"/{collection}/{name}")
        reset = isinstance(result, dict) and "reset" in result
        verb = "Reset" if reset else "Deleted"
        typer.echo(f"{verb} {collection}/{name}.")
        note = result.get("note") if isinstance(result, dict) else None
        if note:
            # a collection may have a consequence worth hearing at the moment
            # of the delete rather than at the moment it takes effect (#167)
            typer.echo(str(note))

    return group
