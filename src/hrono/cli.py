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

from hrono.crypto.masterkey import (
    InvalidKey,
    KeyFileUnreadable,
    KeyNotProvided,
    MasterKeyError,
    load_key,
)
from hrono.server.app import create_app

app = typer.Typer(add_completion=False)

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
    try:
        key = load_key(key_file, os.environ.get("HRONO_MASTER_KEY"))
    except MasterKeyError as exc:
        typer.echo(_key_error_message(exc), err=True)
        raise typer.Exit(1) from exc

    uvicorn.run(create_app(master_key=key), host=host, port=port)


def _key_error_message(exc: MasterKeyError) -> str:
    builder = _KEY_ERRORS.get(type(exc))
    return builder(exc) if builder else str(exc)
