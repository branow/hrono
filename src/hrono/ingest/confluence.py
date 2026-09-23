"""The ``confluence`` source type: the pages of its scoped spaces (T42).

The first type with no git anywhere in it. What is confluence's and nothing
else's is here — the scope selectors, the two endpoints, basic auth, and the
shape of a page — while pulling, materializing, versioning and reading back
are ``pages``', shared with notion.

Three decisions worth stating, because they are not free choices:

- a page's unit path is ``space-<KEY>/page-<ID>.html``. The splitters pick a
  grammar by EXTENSION (#143), and what confluence returns is storage-format
  XHTML, so that is what it is called and what is stored. No conversion is
  hidden inside the reader: what hrono ingests is what the provider sent.
- a page's version is its ``version.number``, carried per unit, so editing one
  page does not re-ingest its space.
- the address is ``confluence://<site host>/space-<KEY>/page-<ID>.html@<n>``,
  which is the design sketch's identity with #144's fragment removed.
"""

from __future__ import annotations

import base64
from collections.abc import Iterator, Sequence
from pathlib import Path
from urllib.parse import urlparse

from hrono.ingest import SyncError
from hrono.ingest.api import TIMEOUT, get_json
from hrono.ingest.pages import Page, materialize

LIMIT = 50


def confluence_sync(
    config: dict[str, object],
    cache: Path,
    timeout: float,
    *,
    fetch: object = None,
) -> str:
    """Pull every page in scope into the cache; return the source version."""
    return materialize(
        cache, tuple(pages(config, fetch=fetch, timeout=timeout))
    )


def pages(
    config: dict[str, object],
    *,
    fetch: object = None,
    timeout: float = TIMEOUT,
) -> Iterator[Page]:
    """Every page the scope selects, deduplicated by id.

    Scopes are UNIONED (implementation-notes), so the same page reached through
    both a space selector and a page selector is pulled once.
    """
    getter = fetch if fetch is not None else get_json
    base = _base(config)
    headers = _headers(config.get("auth"))
    seen: set[str] = set()
    for selector in _selectors(config):
        for raw in _select(getter, base, headers, selector, timeout):
            page = _page(raw)
            if page is None or page.path in seen:
                continue
            seen.add(page.path)
            yield page


def _selectors(config: dict[str, object]) -> tuple[dict[str, object], ...]:
    """An empty scope, or one naming ``all``, means everything visible."""
    scope = config.get("scope")
    if not isinstance(scope, list) or not scope:
        return ({"type": "all"},)
    chosen = tuple(s for s in scope if isinstance(s, dict))
    if any(s.get("type") == "all" for s in chosen):
        return ({"type": "all"},)
    return chosen


def _select(
    getter: object,
    base: str,
    headers: dict[str, str],
    selector: dict[str, object],
    timeout: float,
) -> Iterator[dict[str, object]]:
    kind = str(selector.get("type"))
    if kind == "page":
        url = f"{base}/rest/api/content/{selector['id']}?expand={_EXPAND}"
        status, body = getter(url, headers, timeout)  # type: ignore[operator]
        _raise_for(status, kind)
        if isinstance(body, dict):
            yield body
        return
    if kind == "space":
        query = f"spaceKey={selector['key']}&"
    elif kind == "all":
        query = ""
    else:
        raise SyncError(f"unsupported confluence scope selector: {kind}")
    url = f"{base}/rest/api/content?{query}limit={LIMIT}&expand={_EXPAND}"
    while url:
        status, body = getter(url, headers, timeout)  # type: ignore[operator]
        _raise_for(status, kind)
        if not isinstance(body, dict):
            raise SyncError("confluence returned an unexpected body")
        results: Sequence[object] = body.get("results") or ()
        for entry in results:
            if isinstance(entry, dict):
                yield entry
        url = _next(body, base)


_EXPAND = "body.storage,version,space"


def _next(body: dict[str, object], base: str) -> str | None:
    """Atlassian pages with a relative ``_links.next``; resolve it."""
    links = body.get("_links")
    if not isinstance(links, dict):
        return None
    nxt = links.get("next")
    if not isinstance(nxt, str) or not nxt:
        return None
    return nxt if nxt.startswith("http") else f"{base}{nxt}"


def _page(raw: dict[str, object]) -> Page | None:
    page_id = str(raw.get("id") or "")
    space = raw.get("space")
    key = str(space.get("key")) if isinstance(space, dict) else ""
    version = raw.get("version")
    number = version.get("number") if isinstance(version, dict) else None
    body = raw.get("body")
    storage = body.get("storage") if isinstance(body, dict) else None
    text = storage.get("value") if isinstance(storage, dict) else None
    if not page_id or not key or number is None or not isinstance(text, str):
        return None
    return Page(
        path=f"space-{key}/page-{page_id}.html",
        body=text.encode(),
        version=str(number),
    )


def _raise_for(status: int, kind: str) -> None:
    if status == 404:
        raise SyncError(f"confluence found no content for scope: {kind}")
    if status in (401, 403):
        raise SyncError("confluence refused the credentials")
    if status != 200:
        raise SyncError(f"confluence returned {status}")


def confluence_instance(config: dict[str, object], cache: Path) -> str:
    """The site's host: the base url without scheme, path or credentials."""
    return urlparse(_base(config)).netloc


def validate_confluence(
    config: dict[str, object],
    context: object = None,
    *,
    fetch: object = None,
    timeout: float = TIMEOUT,
) -> None:
    """Reject the write unless the site answers and the credential works."""
    from hrono.registry.descriptor import ValidationFailed

    getter = fetch if fetch is not None else get_json
    status, _body = getter(  # type: ignore[operator]
        f"{_base(config)}/rest/api/space?limit=1",
        _headers(config.get("auth")),
        timeout,
    )
    if status == 200:
        return
    if status in (401, 403):
        raise ValidationFailed("authentication failed")
    if status == 404:
        raise ValidationFailed("that base url is not a confluence site")
    raise ValidationFailed(f"confluence returned {status}")


def _base(config: dict[str, object]) -> str:
    return str(config["base_url"]).rstrip("/")


def _headers(auth: object) -> dict[str, str]:
    """Atlassian's api token is BASIC auth with the account email as user."""
    headers = {"Accept": "application/json"}
    if isinstance(auth, dict) and auth.get("method") == "basic":
        pair = f"{auth.get('email', '')}:{auth.get('token', '')}"
        encoded = base64.b64encode(pair.encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
    return headers


__all__ = [
    "confluence_instance",
    "confluence_sync",
    "pages",
    "validate_confluence",
]
