"""The ``hrono`` command-line entry point.

Only ``serve`` exists today; it runs the server. The client subcommands
(``recall``, ``sources``, ...) that make this a thin HTTP client land with the
CLI foundation milestone.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from hrono.auth.bootstrap import BOOTSTRAP_ADMIN, bootstrap_admin
from hrono.context.commands import app as context_app
from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import (
    InvalidKey,
    KeyFileUnreadable,
    KeyNotProvided,
    MasterKeyError,
    load_key,
    reconcile,
)
from hrono.db.database import DEFAULT_PATH, open_database
from hrono.registry.collections import COLLECTIONS
from hrono.registry.seeding import seed_defaults
from hrono.server.app import create_app

app = typer.Typer(add_completion=False)
app.add_typer(context_app, name="context")

_KEY_ERRORS: dict[type[MasterKeyError], Callable[[MasterKeyError], str]] = {
    KeyNotProvided: lambda _: (
        "No master key provided. Supply it with --key-file <path> or the "
        "HRONO_MASTER_KEY environment variable."
    ),
    KeyFileUnreadable: lambda exc: (
        f"Cannot read master key file: {exc.path}"  # type: ignore[attr-defined]
    ),
    InvalidKey: lambda _: (
        "Master key is not a valid Fernet key (expected a url-safe "
        "base64-encoded 32-byte key)."
    ),
}


@app.callback()
def main() -> None:
    """hrono — a hierarchical knowledge base for AI agents."""


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
        typer.echo(_key_error_message(exc), err=True)
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


def _key_error_message(exc: MasterKeyError) -> str:
    builder = _KEY_ERRORS.get(type(exc))
    return builder(exc) if builder else str(exc)


def _bootstrap_message(token: str) -> str:
    return (
        "\nThe users table was empty, so a bootstrap admin was created.\n"
        f"  user:  {BOOTSTRAP_ADMIN}\n"
        "  role:  admin\n"
        f"  token: {token}\n"
        "\nThis token is shown ONCE and is stored only as a hash.\n"
        "Save it now. Authenticate with it as a Bearer token:\n"
        "  Authorization: Bearer <token>\n"
    )
