"""The Export page: what an agent will be handed, before it is handed.

Export is the deliverable, and this page shows it outside a terminal. Here a
curator chooses the hop limit, presses Export, reads the shape the export
reports, pages through the rendered files in place by following their own
links, downloads the same files as one archive, and copies the command that
writes them to a folder.

Building an export renders every file in the tree, so the page never builds
one. The Export button starts the ``export`` op, which stores the result
(``export.saved``); viewing a page and downloading the archive read that
stored copy. It comes from ``export.produce``, the function the API's manifest
and archive come from, so it holds the same files the CLI writes.

A topic whose brief is missing or was stored flagged is listed before anything
else, because the root page is the first thing an agent reads and a brief that
is not a brief there misleads every traversal below it.
"""

from __future__ import annotations

import posixpath
import shlex
import sqlite3
from collections.abc import Callable
from urllib.parse import quote, urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from hrono.errors import NotFound
from hrono.export import saved as saved_export
from hrono.export.collapse import WIDTH
from hrono.export.saved import ROOT_PAGE
from hrono.jobs.worker import enqueue
from hrono.server import prose
from hrono.server.ui import Reader, Writer, _fields, _trees, router, templates

DEFAULT_LEVELS = 4
OP = "export"


@router.get("/ui/trees/{tree}/export", response_class=HTMLResponse)
def export_page(
    request: Request,
    user: Reader,
    tree: str,
    page: str = ROOT_PAGE,
) -> Response:
    """The kept export: its shape, one rendered page, a download."""
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        built = _built(conn, tree)
        kept = saved_export.load(conn, tree)
        running = _running(conn, tree)
    levels = kept.levels if kept is not None else DEFAULT_LEVELS
    context: dict[str, object] = {
        "user": user,
        "trees": trees,
        "tree": tree,
        "levels": levels,
        "built": built,
        "exported": kept is not None,
        "running": running,
        "snippets": connect_snippets(
            str(request.base_url).rstrip("/"), tree, levels
        ),
        "can_write": user.role in {"writer", "admin"},
    }
    if kept is not None:
        pages = kept.pages()
        shown = page if page in pages else ROOT_PAGE
        context |= {
            "built_at": kept.built_at,
            "shape": kept.shape,
            "budget": WIDTH,
            "files": kept.files,
            "size": kept.size,
            "flagged": [
                {
                    "title": flag.title,
                    "why": flag.why,
                    "link": page_link(tree, flag.page),
                }
                for flag in kept.flagged
            ],
            "page": shown,
            "html": prose.linked(
                kept.read(shown) or "", _resolver(tree, shown, pages)
            ),
            "crumbs": [
                (page_link(tree, path), label) for path, label in _crumbs(shown)
            ],
            "download": f"/ui/trees/{tree}/export.zip",
        }
    return templates.TemplateResponse(request, "export.html", context)


@router.post("/ui/trees/{tree}/export")
async def start_export(tree: str, request: Request, user: Writer) -> Response:
    """Build the export at the chosen hop limit in the background.

    Redirect-after-POST so a refresh does not start a second build.
    """
    raw = (await _fields(request)).get("levels", "")
    levels = int(raw) if raw.isdigit() else DEFAULT_LEVELS
    enqueue(
        request.app.state.db,
        OP,
        {"levels": max(2, levels)},
        tree=tree,
        started_by=user.name,
    )
    said = quote("Started the export. Refresh this page when it finishes.")
    return RedirectResponse(
        f"/ui/trees/{tree}/export?tree={tree}&done={said}", status_code=303
    )


@router.get("/ui/trees/{tree}/export.zip")
def download_export(tree: str, request: Request, _: Reader) -> Response:
    """The kept export as one archive, exactly as it was built."""
    with request.app.state.db.connect() as conn:
        kept = saved_export.load(conn, tree)
    if kept is None:
        raise NotFound(f"tree not exported yet: {tree}")
    return Response(
        kept.archive,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{tree}-export-{kept.levels}.zip"'
            )
        },
    )


def _built(conn: sqlite3.Connection, tree: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM nodes WHERE tree = ? LIMIT 1", (tree,)
    ).fetchone()
    return row is not None


def _running(conn: sqlite3.Connection, tree: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM jobs WHERE tree = ? AND op = ? "
        "AND status IN ('pending', 'running') LIMIT 1",
        (tree, OP),
    ).fetchone()
    return row is not None


TOKEN = "YOUR_TOKEN"


def connect_snippets(
    server: str, tree: str, levels: int
) -> list[tuple[str, str, str]]:
    """The three ways in as (id, heading, text) to paste into a terminal.

    The token is a placeholder the reader replaces with their own, never the
    viewer's real one, and every command is a route a reader may call.
    """
    name_arg = shlex.quote(tree)
    base = f"{server}/trees/{quote(tree, safe='')}"
    header = f'-H "Authorization: Bearer {TOKEN}"'
    folder = shlex.quote(f"./{tree}-export")
    return [
        (
            "cli",
            "Ask from the command line",
            f"hrono profile add {name_arg} --server {shlex.quote(server)}"
            f" --token {TOKEN}\n"
            f"hrono profile use {name_arg}\n"
            f'hrono recall {name_arg} "what does this tree know about ...?"',
        ),
        (
            "http",
            "Ask over HTTP",
            f"curl -s -X POST {shlex.quote(base + '/recall')} {header} \\\n"
            '  -H "Content-Type: application/json" \\\n'
            '  -d \'{"question": "what does this tree know about ...?"}\'',
        ),
        (
            "export",
            "Hand over the export",
            f"hrono profile use {name_arg} && \\\n"
            f"hrono tree export {name_arg} -o {folder} --levels {levels}\n"
            f"curl -s {shlex.quote(f'{base}/export.zip?levels={levels}')}"
            f" {header} -o {shlex.quote(tree + '-export.zip')}",
        ),
    ]


def page_link(tree: str, page: str) -> str:
    """The panel's own view of one exported file."""
    query = urlencode({"tree": tree, "page": page})
    return f"/ui/trees/{tree}/export?{query}#page"


def _resolver(
    tree: str, here: str, pages: frozenset[str]
) -> Callable[[str], str]:
    """Map a link inside ``here`` to the panel's view of the file it names."""
    directory = posixpath.dirname(here)

    def resolve(target: str) -> str:
        path = posixpath.normpath(posixpath.join(directory, target))
        return page_link(tree, path) if path in pages else "#page"

    return resolve


def _crumbs(page: str) -> list[tuple[str, str]]:
    """The folders from the root page down to ``page``, each with its brief."""
    parts = page.split("/")[:-1]
    trail = [(ROOT_PAGE, ROOT_PAGE)]
    for depth in range(1, len(parts) + 1):
        trail.append(("/".join(parts[:depth]) + "/brief.md", parts[depth - 1]))
    return trail
