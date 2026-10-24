"""The ``hrono`` command-line entry point.

``serve`` runs the server and owns the database; everything else is a thin HTTP
client of it, so the CLI and the future dashboard see one surface.

The operator verb is ``hrono tree sync <name>`` — one command that brings a
knowledge base up to date. ``hrono tree maintain`` is the cold
build. The lifecycle's individual stages are deliberately NOT commands: they
must run in a particular order and a wrong order produces a map that looks right
and is quietly wrong, so they live behind an admin-only HTTP door.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from hrono.admin.commands import app as admin_app
from hrono.admin.reset import targets, wipe
from hrono.auth.bootstrap import BOOTSTRAP_ADMIN, bootstrap_admin
from hrono.cli_boundary import Boundary
from hrono.client.http import from_profile
from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import load_key, reconcile
from hrono.db.database import open_database
from hrono.db.lock import exclusive
from hrono.errors import AppError
from hrono.jobs.commands import app as jobs_app
from hrono.paths import ENV_DB, database_path
from hrono.profile.commands import app as profile_app
from hrono.registry.collections import COLLECTIONS
from hrono.registry.commands import build_app
from hrono.registry.seeding import seed_defaults
from hrono.server.app import create_app
from hrono.tree.commands import app as tree_app
from hrono.usage.commands import usage

app = typer.Typer(cls=Boundary, no_args_is_help=True)
app.add_typer(profile_app, name="profile")
app.add_typer(admin_app, name="admin")
app.add_typer(tree_app, name="tree")
app.add_typer(jobs_app, name="jobs")
app.command("usage")(usage)
# `trees` config hangs under `hrono tree config` rather than beside it: a
# `hrono trees` next to `hrono tree` reads as a typo, and the work commands and
# the config for the same noun belong together.
tree_app.add_typer(build_app("trees"), name="config")
for _descriptor in COLLECTIONS:
    if _descriptor.collection != "trees":
        app.add_typer(
            build_app(_descriptor.collection), name=_descriptor.collection
        )


# A recall that finds a WARM server answers in milliseconds (measured: 14ms over
# 34 passages once the encoder is cached). This budget is for the cold one: a
# server whose startup warm-up has not finished, or that had no embedding model
# registered when it booted, pays the weights once -- 13.3s on the machine this
# was measured on, and more on a slower disk or a larger model. The registry
# CRUD default of 10s is too short for it.
RECALL_TIMEOUT = 120.0


@app.command()
def recall(
    tree_or_question: Annotated[
        str,
        typer.Argument(
            metavar="[TREE] QUESTION",
            help="A tree name followed by the question — or the question "
            "alone, answered from the profile's default tree.",
        ),
    ],
    question: Annotated[str | None, typer.Argument(hidden=True)] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", help="At most this many passages back."),
    ] = 10,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Print the raw hits as JSON."),
    ] = False,
) -> None:
    """Recall passages from a tree for a question (the fast read door).

    With two arguments the first names the tree; with one, the tree is the
    current profile's --default-tree (or 'default'):

      hrono recall "how does auth work"

      hrono recall beta "how does auth work"
    """
    if question is None:
        tree, asked = _default_tree(), tree_or_question
    else:
        tree, asked = tree_or_question, question
    result = from_profile().post(
        f"/trees/{tree}/recall",
        {"question": asked, "limit": limit},
        timeout=RECALL_TIMEOUT,
    )
    if as_json:
        typer.echo(json.dumps(result, indent=2))
        return
    hits = result.get("hits") if isinstance(result, dict) else []
    message = result.get("message") if isinstance(result, dict) else None
    if not hits:
        typer.echo(message or "no hits.")
        return
    for hit in hits:
        typer.echo(f"[{hit.get('kind', '?')}] {hit.get('header', '')}")
        typer.echo(hit.get("body", ""))
        typer.echo("")


def _default_tree() -> str:
    """The current profile's --default-tree, or 'default'."""
    from hrono.profile.store import Store, config_path

    active = Store(config_path()).current()
    if active is not None and active.default_tree:
        return active.default_tree
    return "default"


def _version(wanted: bool) -> None:
    if not wanted:
        return
    from importlib.metadata import PackageNotFoundError, version

    try:
        typer.echo(f"hrono {version('hrono')}")
    except PackageNotFoundError:
        typer.echo("hrono (version unknown — not installed as a package)")
    raise typer.Exit(0)


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Print the version and exit.",
            callback=_version,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """hrono — a hierarchical knowledge base for AI agents."""


@app.command()
def reset(
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip the confirmation prompt."),
    ] = False,
    db: Annotated[
        Path | None,
        typer.Option("--db", help=f"Database path (or ${ENV_DB})."),
    ] = None,
) -> None:
    """Wipe the local hrono database to recover from a lockout.

    DESTROYS ALL DATA — users, registries (with their encrypted secrets), jobs,
    and ingested content: the synced source clones beside the database go with
    it, so the next run starts clean. The next 'hrono serve' re-applies
    migrations onto a fresh file and bootstraps a new admin token.
    Requires no Bearer token and no master key; its trust boundary is filesystem
    access. Run it while the server is stopped. Confirm interactively, or pass
    --force for non-interactive use.
    """
    db_path = database_path(db)
    doomed = targets(db_path)
    if not doomed:
        typer.echo(f"No hrono database at {db_path}: nothing to reset.")
        return
    if not force:
        typer.echo("This DESTROYS ALL DATA in the hrono database:")
        for path in doomed:
            typer.echo(f"  {path}")
        if not typer.confirm("Delete everything and start over?"):
            typer.echo("Aborted; nothing was changed.", err=True)
            raise typer.Exit(1)
    try:
        # the help has always said "run it while the server is stopped", and
        # nothing checked: this is the same flock `serve` holds, so a reset
        # against a live server is refused instead of deleting the database
        # out from under it.
        with exclusive(db_path):
            removed = wipe(db_path)
    except AppError as exc:
        # a wipe that stopped part-way still owes the operator the list of what
        # it destroyed — that report is what recovery is planned from. The
        # MESSAGE is the boundary's job; this handler exists only for
        # the report, and re-raises.
        _report_removed(_removed_so_far(exc))
        raise
    _report_removed(removed)
    typer.echo("Run 'hrono serve' to bootstrap a fresh admin token.")


def _removed_so_far(error: AppError) -> tuple[Path, ...]:
    done = (error.details or {}).get("removed")
    return (
        tuple(Path(str(path)) for path in done)
        if isinstance(done, list)
        else ()
    )


def _report_removed(removed: tuple[Path, ...]) -> None:
    if not removed:
        return
    typer.echo("Removed:")
    for path in removed:
        typer.echo(f"  {path}")


@app.command()
def serve(
    host: Annotated[
        str,
        typer.Option(
            "--host",
            help="Interface to listen on; 0.0.0.0 exposes it to the network.",
        ),
    ] = "127.0.0.1",
    port: Annotated[
        int, typer.Option("--port", help="Port to listen on.")
    ] = 8080,
    key_file: Annotated[
        Path | None,
        typer.Option(
            "--key-file",
            help=(
                "Master key file — every stored secret is encrypted under it. "
                "Make one with 'hrono admin new-key --out <path>', or set "
                "$HRONO_MASTER_KEY instead."
            ),
        ),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option(
            "--db",
            help=f"Database path (or ${ENV_DB}). The default, "
            ".hrono/hrono.db, is RELATIVE to the directory serve runs from.",
        ),
    ] = None,
) -> None:
    """Run the hrono HTTP server (owns the database and all compute).

    The database path anchors everything else: the synced source clones live in
    <db parent>/cache/sources, so two servers started from different directories
    against the same --db share one cache instead of re-cloning. The default
    path is relative to the CURRENT DIRECTORY — starting serve somewhere else
    quietly begins a fresh, empty database, which is why the resolved path is
    printed first.
    """
    db_path = database_path(db)
    typer.echo(f"Database: {db_path.resolve()}")
    key = load_key(key_file, os.environ.get("HRONO_MASTER_KEY"))
    with exclusive(db_path):
        _bootstrap(key, db_path, host, port)
        uvicorn.run(
            create_app(db_path=db_path, master_key=key),
            host=host,
            port=port,
            # open SSE watchers otherwise hold the shutdown open, and the
            # lifespan's worker stop (which releases the claimed job) never
            # runs until every stream closes on its own.
            timeout_graceful_shutdown=10,
        )


def _bootstrap(key: bytes, db_path: Path, host: str, port: int) -> None:
    """Reconcile the master key, seed defaults, and print a first-run token."""
    connection = open_database(db_path)
    try:
        record = reconcile(connection, key)
        token = bootstrap_admin(connection)
        if token is not None:
            typer.echo(_bootstrap_message(token, host, port))
        seed_defaults(
            connection, Cipher.from_key(key, record.key_id), COLLECTIONS
        )
    finally:
        connection.close()


def _bootstrap_message(token: str, host: str, port: int) -> str:
    """The first-run hint, addressed at the server the user actually started.

    It must not print a literal ``http://127.0.0.1:8080`` whatever ``--host``
    and ``--port`` were given, because the one copy-pasteable line in hrono's
    first-run experience would point somewhere that is not listening. A hint
    that does not work is worse than no hint.
    """
    return (
        "\nThe users table was empty, so a bootstrap admin was created.\n"
        f"  user:  {BOOTSTRAP_ADMIN}\n"
        "  role:  admin\n"
        f"  token: {token}\n"
        "\nThis token is shown ONCE and is stored only as a hash. "
        "Save it now.\n"
        "Use it with the CLI:\n"
        f"  hrono profile add local --server http://{host}:{port} "
        "--token <token>\n"
        "or call the API directly with a Bearer token:\n"
        "  Authorization: Bearer <token>\n"
        "\nThe dashboard is the same token in a browser:\n"
        f"  http://{host}:{port}/ui\n"
    )
