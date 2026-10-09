"""The ``notion`` source type: the pages shared with an integration.

Notion differs from confluence in one structural way: there is no document to
fetch. A page is a TREE OF BLOCKS, so the syncer renders it — paragraphs,
headings, list items, quotes and code become markdown-shaped lines, and any
other block contributes whatever plain text it carries rather than vanishing.
The rendering is deliberately small: hrono splits and summarises prose, and a
faithful reproduction of Notion's formatting would buy nothing downstream.

An integration only sees what has been shared with it (``docs/api.md``),
so "everything" is not an admin question — it is `POST /v1/search`, which
returns exactly what this token can read. The workspace in a page's address
comes from the token's own bot (`GET /v1/users/me`) rather than from user
config, which could disagree with the token and silently split one workspace's
pages across two identities.

Identity: ``notion://<workspace>/page-<id>.md@<last_edited_time>``, the spec's
own rule, with the version carried per page so editing one does not re-ingest
the rest.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
from urllib.parse import quote

from hrono.ingest import SyncError
from hrono.ingest.api import TIMEOUT, get_json, post_json
from hrono.ingest.pages import Page, materialize

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
PAGE_SIZE = 100

_PREFIX = {
    "heading_1": "# ",
    "heading_2": "## ",
    "heading_3": "### ",
    "bulleted_list_item": "- ",
    "numbered_list_item": "1. ",
    "to_do": "- [ ] ",
    "quote": "> ",
    "code": "    ",
}


def notion_sync(
    config: dict[str, object],
    cache: Path,
    timeout: float,
    *,
    get: object = None,
    post: object = None,
) -> str:
    """Render every page in scope into the cache; return the source version."""
    found = tuple(pages(config, get=get, post=post, timeout=timeout))
    name = workspace(config, get=get, timeout=timeout)
    version = materialize(cache, found)
    (cache / WORKSPACE_FILE).write_text(name)
    return version


def pages(
    config: dict[str, object],
    *,
    get: object = None,
    post: object = None,
    timeout: float = TIMEOUT,
) -> Iterator[Page]:
    """Every page the scope selects, rendered, deduplicated by id."""
    getter = get if get is not None else get_json
    poster = post if post is not None else post_json
    headers = _headers(config.get("auth"))
    seen: set[str] = set()
    for raw in _selected(getter, poster, headers, config, timeout):
        page_id = str(raw.get("id") or "")
        edited = str(raw.get("last_edited_time") or "")
        if not page_id or not edited or page_id in seen:
            continue
        seen.add(page_id)
        body = render(_blocks(getter, headers, page_id, timeout))
        yield Page(
            path=f"page-{page_id}.md", body=body.encode(), version=edited
        )


def _selected(
    getter: object,
    poster: object,
    headers: dict[str, str],
    config: dict[str, object],
    timeout: float,
) -> Iterator[dict[str, object]]:
    for selector in _selectors(config):
        kind = str(selector.get("type"))
        if kind in ("page", "database"):
            url = f"{API}/{'pages' if kind == 'page' else 'databases'}"
            status, body = getter(  # type: ignore[operator]
                f"{url}/{selector['id']}", headers, timeout
            )
            _raise_for(status)
            if kind == "page" and isinstance(body, dict):
                yield body
            elif isinstance(body, dict):
                yield from _database_pages(
                    poster, headers, str(selector["id"]), timeout
                )
        elif kind == "all":
            yield from _search(poster, headers, timeout)
        else:
            raise SyncError(f"unsupported notion scope selector: {kind}")


def _selectors(config: dict[str, object]) -> tuple[dict[str, object], ...]:
    scope = config.get("scope")
    if not isinstance(scope, list) or not scope:
        return ({"type": "all"},)
    chosen = tuple(s for s in scope if isinstance(s, dict))
    if any(s.get("type") == "all" for s in chosen):
        return ({"type": "all"},)
    return chosen


def _search(
    poster: object, headers: dict[str, str], timeout: float
) -> Iterator[dict[str, object]]:
    """Everything shared with this integration, page by page."""
    cursor: str | None = None
    while True:
        body: dict[str, object] = {
            "filter": {"property": "object", "value": "page"},
            "page_size": PAGE_SIZE,
        }
        if cursor:
            body["start_cursor"] = cursor
        status, payload = poster(  # type: ignore[operator]
            f"{API}/search", headers, body, timeout
        )
        cursor = yield from _results(status, payload)
        if cursor is None:
            return


def _database_pages(
    poster: object, headers: dict[str, str], db_id: str, timeout: float
) -> Iterator[dict[str, object]]:
    """A database contributes its pages; the rows themselves are not read."""
    cursor: str | None = None
    while True:
        body: dict[str, object] = {"page_size": PAGE_SIZE}
        if cursor:
            body["start_cursor"] = cursor
        status, payload = poster(  # type: ignore[operator]
            f"{API}/databases/{db_id}/query", headers, body, timeout
        )
        cursor = yield from _results(status, payload)
        if cursor is None:
            return


def _results(status: int, payload: object) -> Iterator[dict[str, object]]:
    """Yield a response's results; return the next cursor, or None when done."""
    _raise_for(status)
    if not isinstance(payload, dict):
        raise SyncError("notion returned an unexpected body")
    entries: Sequence[object] = payload.get("results") or ()
    for entry in entries:
        if isinstance(entry, dict):
            yield entry
    if not payload.get("has_more"):
        return None
    cursor = payload.get("next_cursor")
    return str(cursor) if cursor else None


def _blocks(
    getter: object, headers: dict[str, str], parent: str, timeout: float
) -> list[dict[str, object]]:
    """One level of children, then each child's own, depth first."""
    collected: list[dict[str, object]] = []
    cursor = ""
    while True:
        suffix = f"&start_cursor={cursor}" if cursor else ""
        status, payload = getter(  # type: ignore[operator]
            f"{API}/blocks/{parent}/children?page_size={PAGE_SIZE}{suffix}",
            headers,
            timeout,
        )
        _raise_for(status)
        if not isinstance(payload, dict):
            raise SyncError("notion returned an unexpected body")
        entries: Sequence[object] = payload.get("results") or ()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            collected.append(entry)
            if entry.get("has_children"):
                collected.extend(
                    _blocks(getter, headers, str(entry["id"]), timeout)
                )
        if not payload.get("has_more"):
            return collected
        cursor = str(payload.get("next_cursor") or "")
        if not cursor:
            return collected


def render(blocks: Sequence[dict[str, object]]) -> str:
    """Render blocks to markdown-shaped lines.

    An unknown block contributes its plain text rather than nothing: hrono
    would rather ingest an unstyled paragraph than silently lose a page's
    content to a block type Notion added last week.
    """
    lines: list[str] = []
    for block in blocks:
        kind = str(block.get("type") or "")
        payload = block.get(kind)
        text = _plain(payload)
        if not text:
            continue
        lines.append(f"{_PREFIX.get(kind, '')}{text}")
    return "\n\n".join(lines) + "\n" if lines else ""


def _plain(payload: object) -> str:
    """The concatenated plain text of a block's rich-text runs."""
    if not isinstance(payload, dict):
        return ""
    runs = payload.get("rich_text") or payload.get("text") or ()
    if not isinstance(runs, list):
        return ""
    parts = [
        str(run.get("plain_text", "")) for run in runs if isinstance(run, dict)
    ]
    return "".join(parts).strip()


WORKSPACE_FILE = ".hrono-workspace"


def workspace(
    config: dict[str, object], *, get: object = None, timeout: float = TIMEOUT
) -> str:
    """The workspace this TOKEN belongs to, asked of the token itself."""
    getter = get if get is not None else get_json
    status, body = getter(  # type: ignore[operator]
        f"{API}/users/me", _headers(config.get("auth")), timeout
    )
    _raise_for(status)
    name = ""
    if isinstance(body, dict):
        bot = body.get("bot")
        if isinstance(bot, dict):
            named = bot.get("workspace_name")
            name = str(named) if named else ""
    return name or "workspace"


def notion_instance(config: dict[str, object], cache: Path) -> str:
    """The workspace the SYNC recorded, never a fresh call.

    An address must not depend on a live API call: an ingest that reached the
    provider once should keep addressing its content the same way afterwards,
    offline included, and a workspace renamed between two calls would
    otherwise split one source's pages across two identities.

    A workspace NAME is free text — "Acme HQ" is a normal one — and an
    instance lands verbatim in a URI, so it is percent-encoded here. The cache
    keeps the name as the provider spelled it; only the address is escaped.
    """
    path = cache / WORKSPACE_FILE
    if not path.exists():
        raise SyncError("this source has not been synced yet")
    name = path.read_text().strip() or "workspace"
    return quote(name, safe="")


def validate_notion(
    config: dict[str, object],
    context: object = None,
    *,
    get: object = None,
    timeout: float = TIMEOUT,
) -> None:
    """Reject the write unless the integration token authenticates."""
    from hrono.registry.descriptor import ValidationFailed

    getter = get if get is not None else get_json
    status, _body = getter(  # type: ignore[operator]
        f"{API}/users/me", _headers(config.get("auth")), timeout
    )
    if status == 200:
        return
    if status in (401, 403):
        raise ValidationFailed("authentication failed")
    raise ValidationFailed(f"notion returned {status}")


def _raise_for(status: int) -> None:
    if status == 404:
        raise SyncError("notion has not shared that object with this token")
    if status in (401, 403):
        raise SyncError("notion refused the credentials")
    if status != 200:
        raise SyncError(f"notion returned {status}")


def _headers(auth: object) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Notion-Version": VERSION,
    }
    if isinstance(auth, dict) and auth.get("method") == "token":
        headers["Authorization"] = f"Bearer {auth['token']}"
    return headers


__all__ = [
    "notion_instance",
    "workspace",
    "notion_sync",
    "pages",
    "render",
    "validate_notion",
]
