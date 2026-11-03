"""What an insights pass did to a topic, as the topic page shows it.

The rows are the pass's own (`insights_passes`, `insights_findings`), the
brief it replaced is the topic's kept version (`brief_versions`, reason
'insights'); nothing here is stored for the page.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable

from hrono.ingest.blob_link import blob_url
from hrono.summarize.review import review_item

# a range takes the lower level's tone
_CONFIDENCE = {
    "high": "ok",
    "medium-high": "warn",
    "medium": "warn",
    "low-medium": "plain",
    "low": "plain",
}
_CONFIDENCE_LINE = re.compile(
    r"\s*(?:(?P<level>medium-high|low-medium|high|medium|low)\b[\s,;:.\u2013\u2014-]*)?"
    r"(?P<rest>.*)",
    re.I | re.S,
)


def reviewed(
    conn: sqlite3.Connection,
    tree: str,
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
    failed = _failed_run(
        conn, tree, node_id, name, str(one["passed_at"]) if one else ""
    )
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
    # the model writes "high", or "medium, until X is checked", or "high; the
    # code path is unconditional": a leading level word is the chip, the rest
    # is prose; a confidence with no level word is prose alone
    said = _CONFIDENCE_LINE.match(str(row["confidence"]))
    assert said is not None  # every part is optional
    level = (said["level"] or "").lower()
    return {
        "statement": str(row["statement"]),
        "level": level,
        "tone": _CONFIDENCE.get(level, "plain"),
        "settle": said["rest"].strip(),
        "placement": str(row["placement"]),
        "evidence": [_cite(conn, item) for item in _evidence(row["evidence"])],
    }


def _cite(conn: sqlite3.Connection, item: dict[str, str]) -> dict[str, object]:
    """One evidence path as `path:lines`, linked when its source has a host.

    The link opens the version the review read. A finding stored before that
    was kept links the file's current version and says the version is not
    recorded.
    """
    path = item.get("file", "")
    lines = item.get("lines", "")
    shown = f"{path}:{lines}" if lines else path
    version = item.get("version") or None
    link = _link(conn, path, lines, version)
    return {
        "text": shown,
        "link": link,
        "unrecorded": link is not None and version is None,
    }


def _link(
    conn: sqlite3.Connection, path: str, lines: str, version: str | None
) -> str | None:
    row = conn.execute(
        "SELECT instance, path, version FROM sections WHERE "
        "(path = ?1 OR source || '/' || path = ?1 "
        "OR 'source/' || source || '/' || path = ?1 "
        "OR 'condensed/' || source || '/' || path || '.md' = ?1) "
        "AND source_type = 'git' LIMIT 1",
        (path,),
    ).fetchone()
    if row is None:
        return None
    at = version or row["version"]
    first, _dash, last = lines.partition("-")
    if not first.strip().isdigit():
        return blob_url(row["instance"], row["path"], at, 1, 1)
    start = int(first)
    end = int(last) if last.strip().isdigit() else start
    return blob_url(row["instance"], row["path"], at, start, end)


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


def _failed_run(
    conn: sqlite3.Connection,
    tree: str,
    node_id: int,
    name: str,
    since: str,
) -> str | None:
    """The newest run of the tree that tried to review this topic and did not
    finish, if no pass has been stored on it since.

    Two ways a pass fails. A reply that was no review ends the pass but not
    the run: the entry "<name>: <why>" is in its result, so the needle starts
    at the entry's opening quote (a longer name ending in this one is another
    topic). A provider error fails the run itself, and the failed run's
    details name the item it was on.
    """
    needle = json.dumps(f"{name}: ")[:-1]
    escaped = (
        needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    row = conn.execute(
        "SELECT id, updated_at FROM jobs WHERE tree = ? AND updated_at > ? "
        "AND ((result LIKE ? ESCAPE '\\' AND result LIKE '%\"failed\"%') "
        "OR (status = 'failed' AND "
        "json_extract(error_details, '$.item') = ?)) "
        "ORDER BY updated_at DESC LIMIT 1",
        (tree, since, f"%{escaped}%", review_item(node_id)),
    ).fetchone()
    return str(row["id"]) if row is not None else None
