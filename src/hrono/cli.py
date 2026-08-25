"""The ``hrono`` command-line entry point.

Only ``serve`` exists today; it runs the server. The client subcommands
(``recall``, ``sources``, ...) that make this a thin HTTP client land with the
CLI foundation milestone.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from hrono.admin.commands import app as admin_app
from hrono.admin.reset import targets, wipe
from hrono.auth.bootstrap import BOOTSTRAP_ADMIN, bootstrap_admin
from hrono.client.http import ClientError, from_profile
from hrono.client.http import message as client_message
from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import MasterKeyError, load_key, reconcile
from hrono.db.database import DEFAULT_PATH, open_database
from hrono.errors import AppError, cli_message
from hrono.profile.commands import app as profile_app
from hrono.registry.collections import COLLECTIONS
from hrono.registry.seeding import seed_defaults
from hrono.server.app import create_app
from hrono.tree.commands import app as tree_app

app = typer.Typer(add_completion=False)
app.add_typer(profile_app, name="profile")
app.add_typer(admin_app, name="admin")
app.add_typer(tree_app, name="tree")


@app.command()
def recall(
    tree: str,
    question: str,
    limit: Annotated[int, typer.Option("--limit")] = 10,
) -> None:
    """Recall passages from a tree for a question (the fast read door)."""
    try:
        result = from_profile().post(
            f"/trees/{tree}/recall", {"question": question, "limit": limit}
        )
    except ClientError as exc:
        typer.echo(client_message(exc), err=True)
        raise typer.Exit(1) from exc
    hits = result.get("hits") if isinstance(result, dict) else []
    message = result.get("message") if isinstance(result, dict) else None
    if not hits:
        typer.echo(message or "no hits.")
        return
    for hit in hits:
        typer.echo(f"[{hit['kind']}] {hit['header']}")
        typer.echo(hit["body"])
        typer.echo("")


@app.callback()
def main() -> None:
    """hrono — a hierarchical knowledge base for AI agents."""


@app.command()
def reset(
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip the confirmation prompt."),
    ] = False,
) -> None:
    """Wipe the local hrono database to recover from a lockout.

    DESTROYS ALL DATA — users, registries (with their encrypted secrets), jobs,
    and ingested content. The next 'hrono serve' re-applies migrations onto a
    fresh file and bootstraps a new admin token. Requires no Bearer token and no
    master key; its trust boundary is filesystem access. Run it while the server
    is stopped. Confirm interactively, or pass --force for non-interactive use.
    """
    doomed = targets(DEFAULT_PATH)
    if not doomed:
        typer.echo(f"No hrono database at {DEFAULT_PATH}: nothing to reset.")
        return
    if not force:
        typer.echo("This DESTROYS ALL DATA in the hrono database:")
        for path in doomed:
            typer.echo(f"  {path}")
        if not typer.confirm("Delete everything and start over?"):
            typer.echo("Aborted; nothing was changed.", err=True)
            raise typer.Exit(1)
    try:
        removed = wipe(DEFAULT_PATH)
    except AppError as exc:
        typer.echo(cli_message(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo("Removed:")
    for path in removed:
        typer.echo(f"  {path}")
    typer.echo("Run 'hrono serve' to bootstrap a fresh admin token.")


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8080,
    key_file: Annotated[Path | None, typer.Option("--key-file")] = None,
) -> None:
    """Run the hrono HTTP server (owns the database and all compute)."""
    connection = None
    try:
        key = load_key(key_file, os.environ.get("HRONO_MASTER_KEY"))
        connection = open_database(DEFAULT_PATH)
        record = reconcile(connection, key)
    except MasterKeyError as exc:
        if connection is not None:
            connection.close()
        typer.echo(cli_message(exc), err=True)
        raise typer.Exit(1) from exc

    token = bootstrap_admin(connection)
    if token is not None:
        typer.echo(_bootstrap_message(token))

    seed_defaults(connection, Cipher.from_key(key, record.key_id), COLLECTIONS)

    app = create_app(
        connection=connection, master_key=key, key_id=record.key_id
    )
    try:
        uvicorn.run(app, host=host, port=port)
    finally:
        connection.close()


def _bootstrap_message(token: str) -> str:
    return (
        "\nThe users table was empty, so a bootstrap admin was created.\n"
        f"  user:  {BOOTSTRAP_ADMIN}\n"
        "  role:  admin\n"
        f"  token: {token}\n"
        "\nThis token is shown ONCE and is stored only as a hash. "
        "Save it now.\n"
        "Use it with the CLI:\n"
        "  hrono profile add local --server http://127.0.0.1:8080 "
        "--token <token>\n"
        "or call the API directly with a Bearer token:\n"
        "  Authorization: Bearer <token>\n"
    )
