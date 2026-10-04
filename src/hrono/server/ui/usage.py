"""What was spent: one page for every role, over the ledger's roll-ups (#203).

Everything here is a READ of `hrono.usage.rollup` — the same figures `GET
/usage` and `hrono usage` give — worded by `spend.describe`. A page that did
its own sums would be a third set of numbers to disagree with those two.
"""

from __future__ import annotations

import sqlite3
from typing import cast

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from hrono.recall import log as recall_log
from hrono.server.ui import Reader, _trees, router, templates
from hrono.server.ui.ask import ask_link
from hrono.server.ui.spend import describe
from hrono.usage.rollup import Filter, total, usage

COSTLIEST_RUNS = 10
QUESTIONS = 20
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
        can_write = user.role in {"writer", "admin"}
        asked = _asked(conn, chosen) if can_write else None
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
            "can_write": can_write,
            "asked": asked,
            "window": DAYS,
        },
    )


def _asked(conn: sqlite3.Connection, tree: str) -> dict[str, object]:
    """Agent recall calls: per day, the share that was not confident, latest."""
    days = recall_log.per_day(conn, tree)[-DAYS:]
    calls = sum(day["calls"] for day in days)
    unsure = sum(day["unsure"] for day in days)
    questions = recall_log.latest(conn, tree, QUESTIONS)
    return {
        "days": days,
        "calls": calls,
        "unsure_share": round(100 * unsure / calls) if calls else 0,
        "questions": [
            {
                **row,
                "link": ask_link(tree, str(row["question"])),
            }
            for row in questions
        ],
    }


def _rows(groups: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "key": group["key"],
            "run": group.get("run"),
            **(describe(group) or {}),
        }
        for group in groups
    ]


def _bars(groups: list[dict[str, object]]) -> list[dict[str, object]]:
    """One bar a day, as long as that day's tokens are to the busiest day's."""
    rows = _rows(groups)
    volumes = [cast(int, row["volume"]) for row in rows]
    most = max(volumes, default=0)
    return [
        {**row, "share": round(100 * volume / most) if most else 0}
        for row, volume in zip(rows, volumes, strict=True)
    ]
