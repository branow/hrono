"""``GET /usage``: the ledger rolled up, for any signed-in role."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from hrono.auth.users import User
from hrono.server.auth import require_role
from hrono.usage.rollup import Filter, usage

router = APIRouter()

Reader = Annotated[User, Depends(require_role("reader"))]


@router.get("/usage")
def get_usage(
    request: Request,
    _: Reader,
    by: str = "model",
    tree: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> dict[str, object]:
    """Calls, tokens by kind, model seconds and cost, grouped ``by``.

    ``by`` is one of run, model, upstream-model, user, day. ``since`` and
    ``until`` are ISO timestamps (a date works). Metered spend and the
    subscription estimate are reported apart and never summed.
    """
    with request.app.state.db.connect() as conn:
        groups = usage(conn, by, Filter(tree=tree, since=since, until=until))
    return {"by": by, "groups": groups}
