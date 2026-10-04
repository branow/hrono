"""The Export page (#205): what an agent will be handed, before it is handed.

Export is the deliverable, and until this page a curator could only see it from
a terminal. Here they choose the hop limit, read the shape #204 reports, page
through the rendered files in place by following their own links, download the
same files as one archive, and copy the command that writes them to a folder.

Everything comes from ``export.produce`` — the function the API's manifest and
archive come from — so the panel cannot show a different export from the one
the CLI writes. Every role may use it: export has always been a reader route.

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
from fastapi.responses import HTMLResponse, Response

from hrono.export.collapse import WIDTH
from hrono.export.produce import Export, produce
from hrono.naming import name
from hrono.server import prose
from hrono.server.ui import Reader, _trees, router, templates
from hrono.summarize import briefs

ROOT_PAGE = "root.md"
DEFAULT_LEVELS = 4


@router.get("/ui/trees/{tree}/export", response_class=HTMLResponse)
def export_page(
    request: Request,
    user: Reader,
    tree: str,
    levels: int = DEFAULT_LEVELS,
    page: str = ROOT_PAGE,
) -> Response:
    """The export's shape at ``levels`` hops, one rendered page, a download."""
    levels = max(2, levels)
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        made = produce(conn, tree, levels)
        flagged = [] if made is None else _flagged(conn, made, tree, levels)
    shown = page if made is not None and page in made.files else ROOT_PAGE
    context: dict[str, object] = {
        "user": user,
        "trees": trees,
        "tree": tree,
        "levels": levels,
        "built": made is not None,
        "snippets": connect_snippets(
            str(request.base_url).rstrip("/"), tree, levels
        ),
        "can_write": user.role in {"writer", "admin"},
    }
    if made is not None:
        context |= {
            "shape": made.shape,
            "budget": WIDTH,
            "files": len(made.files),
            "size": sum(
                len(text.encode("utf-8")) for text in made.files.values()
            ),
            "flagged": flagged,
            "page": shown,
            "html": prose.linked(
                made.files[shown], _resolver(tree, levels, shown, made)
            ),
            "crumbs": [
                (page_link(tree, levels, path), label)
                for path, label in _crumbs(shown)
            ],
            "download": f"/trees/{tree}/export.zip?levels={levels}",
        }
    return templates.TemplateResponse(request, "export.html", context)


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
            f"hrono tree export {name_arg} -o {folder} --levels {levels}\n"
            f"curl -s {shlex.quote(f'{base}/export.zip?levels={levels}')}"
            f" {header} -o {shlex.quote(tree + '-export.zip')}",
        ),
    ]


def page_link(tree: str, levels: int, page: str) -> str:
    """The panel's own view of one exported file."""
    query = urlencode({"tree": tree, "levels": levels, "page": page})
    return f"/ui/trees/{tree}/export?{query}#page"


def _resolver(
    tree: str, levels: int, here: str, made: Export
) -> Callable[[str], str]:
    """Map a link inside ``here`` to the panel's view of the file it names."""
    directory = posixpath.dirname(here)

    def resolve(target: str) -> str:
        path = posixpath.normpath(posixpath.join(directory, target))
        return page_link(tree, levels, path) if path in made.files else "#page"

    return resolve


def _crumbs(page: str) -> list[tuple[str, str]]:
    """The folders from the root page down to ``page``, each with its brief."""
    parts = page.split("/")[:-1]
    trail = [(ROOT_PAGE, ROOT_PAGE)]
    for depth in range(1, len(parts) + 1):
        trail.append(("/".join(parts[:depth]) + "/brief.md", parts[depth - 1]))
    return trail


def _flagged(
    conn: sqlite3.Connection, made: Export, tree: str, levels: int
) -> list[dict[str, object]]:
    """Exported topics whose brief is missing or was stored flagged."""
    ids = sorted(made.tree.nodes)
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        "SELECT n.id AS id, b.flagged AS flagged, b.text AS text, "  # noqa: S608
        f"b.node_id AS has, {briefs.TEMPLATE} AS template "
        f"FROM nodes n LEFT JOIN briefs b ON b.node_id = n.id "
        f"WHERE n.id IN ({marks}) ORDER BY n.id",
        ids,
    ).fetchall()
    return [
        {
            "title": name(conn, int(row["id"])),
            "why": "no brief" if row["has"] is None else _refusal(conn, row),
            "link": page_link(tree, levels, _page_of(made, int(row["id"]))),
        }
        for row in rows
        if row["has"] is None or _refusal(conn, row)
    ]


def _refusal(conn: sqlite3.Connection, row: sqlite3.Row) -> str:
    return briefs.refusal(
        conn, int(row["id"]), row["flagged"], row["text"], row["template"]
    )


def _page_of(made: Export, node_id: int) -> str:
    if node_id == made.tree.root:
        return ROOT_PAGE
    suffix = f"-{node_id}/brief.md"
    return next(
        (p for p in sorted(made.files) if p.endswith(suffix)), ROOT_PAGE
    )
