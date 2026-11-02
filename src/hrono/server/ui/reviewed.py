"""What an insights pass did to a topic, as the topic page shows it.

The rows are the pass's own (`insights_passes`, `insights_findings`), the
brief it replaced is the topic's kept version (`brief_versions`, reason
'insights'); nothing here is stored for the page.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable

from hrono.ingest.blob_link import blob_url

_CONFIDENCE = {"high": "ok", "medium": "warn"}


def reviewed(
    conn: sqlite3.Connection,
    node_id: int,
    name: str,
    brief_written: str,
    stamp: Callable[[object], str],
) -> dict[str, object] | None:
    """The topic's latest pass, its findings and what to say about them.

    None when the topic never had a pass and no run failed on it. ``extended``
    says the brief on the page is the one the pass wrote; a brief written
    again since (a rewrite, a regeneration) is not, though the findings stay.
    """
    one = conn.execute(
        "SELECT id, passed_at, model_name, skipped, dropped FROM "
        "insights_passes WHERE node_id = ? ORDER BY passed_at DESC, id DESC "
        "LIMIT 1",
        (node_id,),
    ).fetchone()
    failed = _failed_run(conn, name, str(one["passed_at"]) if one else "")
    if one is None and failed is None:
        return None
    skipped = str(one["skipped"]) if one else ""
    found: list[dict[str, object]] = []
    if one is not None:
        found = [
            _finding(conn, row)
            for row in conn.execute(
                "SELECT statement, evidence, placement, confidence FROM "
                "insights_findings WHERE pass_id = ? ORDER BY position",
                (one["id"],),
            )
        ]
    return {
        "reviewed": one is not None,
        "extended": one is not None
        and not skipped
        and brief_written <= str(one["passed_at"]),
        "model": str(one["model_name"]) if one else "",
        "when": stamp(one["passed_at"]) if one else "",
        "pinned": skipped == "pinned",
        "kept": skipped if skipped not in ("", "pinned", "no findings") else "",
        "findings": found,
        "dropped": _list(one["dropped"]) if one else [],
        "failed": failed,
    }


def _finding(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    # the model writes "high", or "medium, until X is checked": the first word
    # is the level, the rest is what would settle it
    level, _sep, rest = str(row["confidence"]).partition(",")
    level = level.strip().lower()
    return {
        "statement": str(row["statement"]),
        "level": level,
        "tone": _CONFIDENCE.get(level, "plain"),
        "settle": rest.strip(),
        "placement": str(row["placement"]),
        "evidence": [_cite(conn, item) for item in _evidence(row["evidence"])],
    }


def _cite(conn: sqlite3.Connection, item: dict[str, str]) -> dict[str, object]:
    """One evidence path as `path:lines`, linked when its source has a host."""
    path = item.get("file", "")
    lines = item.get("lines", "")
    shown = f"{path}:{lines}" if lines else path
    return {
        "text": shown,
        "link": _link(conn, path, lines),
    }


def _link(conn: sqlite3.Connection, path: str, lines: str) -> str | None:
    row = conn.execute(
        "SELECT instance, version FROM sections WHERE path = ? "
        "AND source_type = 'git' LIMIT 1",
        (path,),
    ).fetchone()
    if row is None:
        return None
    first, _dash, last = lines.partition("-")
    if not first.strip().isdigit():
        return blob_url(row["instance"], path, row["version"], 1, 1)
    start = int(first)
    end = int(last) if last.strip().isdigit() else start
    return blob_url(row["instance"], path, row["version"], start, end)


def _evidence(column: object) -> list[dict[str, str]]:
    found = _loaded(column)
    return [item for item in found if isinstance(item, dict)]


def _list(column: object) -> list[str]:
    return [str(item) for item in _loaded(column)]


def _loaded(column: object) -> list[object]:
    try:
        found = json.loads(str(column or "[]"))
    except ValueError:
        return []
    return found if isinstance(found, list) else []


def _failed_run(conn: sqlite3.Connection, name: str, since: str) -> str | None:
    """The newest run that tried to review this topic and did not finish, if
    no pass has been stored on it since."""
    needle = json.dumps(f"{name}: ")[1:-1]
    escaped = (
        needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    row = conn.execute(
        "SELECT id, updated_at FROM jobs WHERE result LIKE ? ESCAPE '\\' "
        "AND result LIKE '%\"failed\"%' AND updated_at > ? "
        "ORDER BY updated_at DESC LIMIT 1",
        (f"%{escaped}%", since),
    ).fetchone()
    return str(row["id"]) if row is not None else None
