"""The ONE place a CLI error becomes a message and an exit code.

No command group carries its own ``_run`` try/except, because then adding a
command would mean copying error presentation, and a renderer could drift in
one group without anyone noticing. Presentation is not each command's business:
commands raise typed domain errors and this renders them.

It is a data table, not a ladder. ``RENDERERS`` maps an exception type to the
function that turns it into one line; a new domain error is an entry, never a
new ``except``.

Lookup is first-match by ``isinstance``, so ORDER decides when one entry is a
subclass of another. No two entries are related today — ``ClientError``,
``AppError``, ``JSONDecodeError`` and ``UnsafePath`` all descend straight from
``Exception`` — so the order is currently inert, and this is a rule for whoever
adds the entry that changes that, not a description of what happens now.

Applied ONCE, as the Typer group's ``invoke``, which is what makes "no new
boilerplate per command" true rather than aspirational: a command body has no
error handling at all, and everything below the root group — including nested
groups — passes through here.

``JSONDecodeError`` is here because `hrono <collection> set` reads config from a
file the user wrote; a malformed file is their mistake to be told about plainly,
not a traceback.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping

import typer
from click import Context
from typer.core import TyperGroup

from hrono.client.http import (
    ClientError,
    Forbidden,
    NotFound,
    TimedOut,
    Unauthorized,
    Unreachable,
)
from hrono.client.http import message as client_message
from hrono.errors import AppError, cli_message
from hrono.tree.commands import NotAnExport, UnsafePath

EXIT_CODE = 1

RENDERERS: Mapping[type[Exception], Callable[[Exception], str]] = {
    ClientError: lambda exc: client_message(exc),  # type: ignore[arg-type]
    AppError: lambda exc: cli_message(exc),  # type: ignore[arg-type]
    json.JSONDecodeError: lambda exc: f"config is not valid JSON: {exc}",
    UnsafePath: str,  # an export payload that tried to escape its folder
    NotAnExport: str,  # --replace pointed at a folder of other files
    PermissionError: lambda exc: (
        f"permission denied: {getattr(exc, 'filename', None) or exc}"
    ),
}

# Scripts gate on these. One code for every failure meant "server down",
# "wrong token" and "no such tree" were indistinguishable to anything but a
# human reading stderr. First-match by isinstance. 2 is skipped: click already
# uses it for usage errors, and overloading it would make "typo in the
# command" and "server down" the same thing to a script.
EXIT_CODES: Mapping[type[Exception], int] = {
    Unreachable: 3,
    TimedOut: 3,
    Unauthorized: 4,
    Forbidden: 4,
    NotFound: 5,
}


def exit_code(error: Exception) -> int:
    for kind, code in EXIT_CODES.items():
        if isinstance(error, kind):
            return code
    return EXIT_CODE


def render(error: Exception) -> str | None:
    """The line to print for ``error``, or None if it is not ours to render."""
    for kind, renderer in RENDERERS.items():
        if isinstance(error, kind):
            return renderer(error)
    return None


class Boundary(TyperGroup):
    """The root group, wrapped so every command shares one error boundary."""

    def invoke(self, ctx: Context) -> object:
        try:
            return super().invoke(ctx)
        except Exception as exc:  # noqa: BLE001 - re-raised unless it is ours
            line = render(exc)
            if line is None:
                raise
            typer.echo(line, err=True)
            raise typer.Exit(exit_code(exc)) from exc
