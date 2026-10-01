"""The one page where explanation belongs (#197).

Every other page in this dashboard runs to a tight prose budget — a hint on a
mark beside the thing, never a paragraph above it. That rule only works if the
explanation has somewhere to BE, and until now it had nowhere: the vocabulary
lived in a spec outside the repository and in a gitignored working file, so a
person looking at the map could not find out what a topic was without asking.

It reads from the live tree rather than describing a general system: the
numbers in it are this install's, so the pipeline is explained in terms of what
it has actually done here.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from hrono.server.ui import Reader, _trees, router, templates


@router.get("/ui/guide", response_class=HTMLResponse)
def guide_page(request: Request, user: Reader, tree: str = "") -> Response:
    """What hrono is, what it built here, and what every word means."""
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        chosen = tree if tree in trees else trees[0]
        stage = _stages(conn, chosen)
    return templates.TemplateResponse(
        request,
        "guide.html",
        {
            "user": user,
            "trees": trees,
            "tree": chosen,
            "stage": stage,
            "can_write": user.role in {"writer", "admin"},
        },
    )


def _stages(conn: object, tree: str) -> dict[str, object]:
    """What this install has at each step of the pipeline.

    A count of zero is as useful as a large one — it says which step has not
    run yet, which is the question somebody reading this page on a half-built
    tree actually has.
    """

    def count(sql: str, *args: object) -> int:
        return int(conn.execute(sql, args).fetchone()[0])  # type: ignore[attr-defined]

    return {
        "sources": count(
            "SELECT COUNT(*) FROM registry WHERE collection = 'sources'"
        ),
        "sections": count(
            "SELECT COUNT(*) FROM sections WHERE source_type != 'node'"
        ),
        "passages": count("SELECT COUNT(*) FROM passages"),
        "condensations": count("SELECT COUNT(*) FROM condensations"),
        "topics": count("SELECT COUNT(*) FROM nodes WHERE tree = ?", tree),
        "briefs": count(
            "SELECT COUNT(*) FROM briefs b JOIN nodes n ON n.id = b.node_id "
            "WHERE n.tree = ?",
            tree,
        ),
        "levels": count(
            "SELECT COUNT(DISTINCT level) FROM nodes WHERE tree = ?", tree
        ),
        "parked": count("SELECT COUNT(*) FROM pending WHERE tree = ?", tree),
    }
