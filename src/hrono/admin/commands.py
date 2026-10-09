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
from cryptography.fernet import Fernet

from hrono.auth.users import reset_token as reissue
from hrono.db.database import open_database
from hrono.db.lock import exclusive
from hrono.paths import ENV_DB, database_path

app = typer.Typer(
    add_completion=False,
    help=(
        "Local recovery commands. These act on the hrono database file "
        "directly and bypass API authentication by design; their trust "
        "boundary is filesystem access, so they need no token and no key."
    ),
)


@app.command("new-key")
def new_key(
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write the key here instead of stdout."),
    ] = None,
) -> None:
    """Generate a master key: the key every stored secret is encrypted under.

    A new install needs one before `hrono serve` will start, and nothing else
    can make one — which is why this exists. Written with owner-only
    permissions when `--out` is given, because a key file the group can read is
    not a key file.
    """
    key = Fernet.generate_key()
    if out is None:
        typer.echo(key.decode())
        return
    if out.exists():
        typer.echo(
            f"{out} already exists. Refusing to overwrite a master key: "
            "if the database was encrypted under it, replacing it makes every "
            "stored secret unreadable.",
            err=True,
        )
        raise typer.Exit(1)
    out.write_bytes(key)
    out.chmod(0o600)
    typer.echo(
        f"Wrote a new master key to {out} (permissions 0600).\n"
        f"Start the server with it:\n"
        f"  hrono serve --key-file {out}\n"
        "Back it up. Lose it and every stored secret is unreadable."
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
    # the same flock `serve` holds: opening the database also MIGRATES it,
    # and a newer CLI silently migrating a file a running server still uses
    # is a recovery command corrupting the thing it recovers.
    with exclusive(db_path):
        connection = open_database(db_path)
        try:
            record, token = reissue(connection, user)
        finally:
            connection.close()
    typer.echo(_reset_message(record.name, record.role, token))


def _reset_message(name: str, role: str, token: str) -> str:
    """The recovery hint, pointed at the step that actually works.

    It must not suggest `profile add local` with a hardcoded port: in
    recovery a `local` profile almost always EXISTS, so that command would
    fail with "already exists", at the exact moment the user is locked out.
    """
    return (
        f"\nReissued the API token for user '{name}'.\n"
        f"  user:  {name}\n"
        f"  role:  {role}\n"
        f"  token: {token}\n"
        "\nThis token is shown ONCE and is stored only as a hash. "
        "Save it now.\n"
        "The previous token no longer works. Record the new one on your "
        "profile:\n"
        "  hrono profile set-token <profile>   (prompts for the token)\n"
        "or, if no profile exists yet:\n"
        "  hrono profile add local --server <server url>\n"
        "or call the API directly with a Bearer token:\n"
        "  Authorization: Bearer <token>\n"
    )
