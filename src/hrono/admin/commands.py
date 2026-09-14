"""The ``hrono admin`` recovery commands.

These operate on the local hrono database file directly and bypass API
authentication by design: their trust boundary is filesystem access to the
database (the same access that could edit sqlite by hand), so they require no
Bearer token and no master key. They exist to recover when no working token is
left — losing the once-shown bootstrap admin token would otherwise lock the API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from hrono.auth.users import reset_token as reissue
from hrono.db.database import open_database
from hrono.errors import AppError, cli_message
from hrono.paths import ENV_DB, database_path

app = typer.Typer(
    add_completion=False,
    help=(
        "Local recovery commands. These act on the hrono database file "
        "directly and bypass API authentication by design; their trust "
        "boundary is filesystem access, so they need no token and no key."
    ),
)


@app.command("reset-token")
def reset_token(
    user: str,
    db: Annotated[
        Path | None,
        typer.Option("--db", help=f"Database path (or ${ENV_DB})."),
    ] = None,
) -> None:
    """Reissue a user's API token against the local DB; prints it once.

    Requires no Bearer token and no master key: filesystem access to the
    database is the trust boundary. Use it to recover when the only token was
    lost, such as the bootstrap admin token. ``--db`` picks the database the
    same way ``serve`` does, so recovery does not depend on the directory the
    command runs in.
    """
    db_path = database_path(db)
    if not db_path.exists():
        typer.echo(
            f"No hrono database at {db_path}: nothing to reset. "
            "Run 'hrono serve' first to create and bootstrap it.",
            err=True,
        )
        raise typer.Exit(1)
    connection = open_database(db_path)
    try:
        record, token = reissue(connection, user)
    except AppError as exc:
        typer.echo(cli_message(exc), err=True)
        raise typer.Exit(1) from exc
    finally:
        connection.close()
    typer.echo(_reset_message(record.name, record.role, token))


def _reset_message(name: str, role: str, token: str) -> str:
    return (
        f"\nReissued the API token for user '{name}'.\n"
        f"  user:  {name}\n"
        f"  role:  {role}\n"
        f"  token: {token}\n"
        "\nThis token is shown ONCE and is stored only as a hash. "
        "Save it now.\n"
        "The previous token no longer works. Use the new one with the CLI:\n"
        "  hrono profile add local --server http://127.0.0.1:8080 "
        "--token <token>\n"
        "or call the API directly with a Bearer token:\n"
        "  Authorization: Bearer <token>\n"
    )
