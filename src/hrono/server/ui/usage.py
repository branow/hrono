"""What was spent: one page for every role, over the ledger's roll-ups (#203).

Everything here is a READ of `hrono.usage.rollup` — the same figures `GET
/usage` and `hrono usage` give — worded by `spend.describe`. A page that did
its own sums would be a third set of numbers to disagree with those two.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from hrono.server.ui import Reader, _trees, router, templates
from hrono.server.ui.spend import describe
from hrono.usage.rollup import Filter, total, usage

COSTLIEST_RUNS = 10
DAYS = 30


@router.get("/ui/usage", response_class=HTMLResponse)
def usage_view(request: Request, user: Reader, tree: str = "") -> Response:
    """Spend over time, per model, the costliest runs, and per person."""
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        chosen = tree if tree in trees else trees[0]
        where = Filter(tree=chosen)
        everything = describe(total(conn, where))
        days = _bars(usage(conn, "day", where)[-DAYS:])
        models = _rows(usage(conn, "model", where))
        runs = _rows(usage(conn, "run", where)[:COSTLIEST_RUNS])
        people = _rows(usage(conn, "user", where))
    return templates.TemplateResponse(
        request,
        "usage.html",
        {
            "user": user,
            "trees": trees,
            "tree": chosen,
            "total": everything,
            "days": days,
            "models": models,
            "runs": runs,
            "people": people,
            "can_write": user.role in {"writer", "admin"},
        },
    )


def _rows(groups: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {"key": group["key"], "run": group.get("run"), **describe(group)}  # type: ignore[dict-item]
        for group in groups
    ]


def _bars(groups: list[dict[str, object]]) -> list[dict[str, object]]:
    """One bar a day, as long as that day's tokens are to the busiest day's."""
    rows = _rows(groups)
    most = max((int(row["volume"]) for row in rows), default=0)  # type: ignore[call-overload]
    return [
        {**row, "share": round(100 * int(row["volume"]) / most) if most else 0}  # type: ignore[call-overload]
        for row in rows
    ]
