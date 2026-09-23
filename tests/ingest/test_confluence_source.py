"""#149: a confluence source ingests the pages of its scoped spaces.

The first type with nothing to clone. What these pin is the part that is
confluence's: the scope selectors and their union, `_links.next` pagination,
the page shape, and the rule that a page carries its OWN version so one edit
does not re-ingest a space. Materializing and reading back are `pages`',
shared with notion and pinned here through the real ops.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from hrono.db.database import Database
from hrono.ingest import SyncError
from hrono.ingest.confluence import (
    confluence_instance,
    confluence_sync,
    pages,
    validate_confluence,
)
from hrono.ingest.split_op import split_source
from hrono.ingest.sync import sync
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.registry import store as registry_store
from hrono.registry.descriptor import ValidationFailed

SITE = "acme.atlassian.net"
PLACEHOLDER = "x" * 12  # stands in for the api credential; never a real one
EXPAND = "body.storage,version,space"


class _Handler(BaseHTTPRequestHandler):
    payloads: dict[str, tuple[int, object]] = {}
    seen: list[str] = []

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's name
        _Handler.seen.append(self.path)
        status, body = _Handler.payloads.get(self.path, (404, {}))
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args: object) -> None:
        return


@pytest.fixture
def site() -> Iterator[str]:
    _Handler.payloads = {}
    _Handler.seen = []
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/wiki"
    finally:
        server.shutdown()
        server.server_close()


def _content(page_id: str, key: str, version: int, html: str) -> dict:
    return {
        "id": page_id,
        "space": {"key": key},
        "version": {"number": version},
        "body": {"storage": {"value": html}},
    }


def _listing(key: str | None, entries: list[dict], nxt: str | None = None):
    body: dict[str, object] = {"results": entries}
    if nxt:
        body["_links"] = {"next": nxt}
    query = f"spaceKey={key}&" if key else ""
    return f"/wiki/rest/api/content?{query}limit=50&expand={EXPAND}", (
        200,
        body,
    )


def _config(site: str, scope: list[dict] | None = None) -> dict:
    return {
        "name": "wiki",
        "type": "confluence",
        "base_url": site,
        "auth": {
            "method": "basic",
            "email": "person@example.com",
            "token": PLACEHOLDER,
        },
        "scope": scope,
    }


def test_a_space_selector_pulls_that_spaces_pages(site: str) -> None:
    path, payload = _listing(
        "ENG",
        [
            _content("1", "ENG", 7, "<p>Onboarding</p>"),
            _content("2", "ENG", 3, "<p>Deploys</p>"),
        ],
    )
    _Handler.payloads = {path: payload}

    found = list(pages(_config(site, [{"type": "space", "key": "ENG"}])))

    assert [p.path for p in found] == [
        "space-ENG/page-1.html",
        "space-ENG/page-2.html",
    ]
    assert [p.version for p in found] == ["7", "3"]  # each its own
    assert found[0].body == b"<p>Onboarding</p>"


def test_pagination_follows_the_relative_next_link(site: str) -> None:
    first_path, first = _listing(
        "ENG",
        [_content("1", "ENG", 1, "<p>a</p>")],
        # Atlassian returns `next` relative to `_links.base`, which is the
        # site url INCLUDING its /wiki context path — so the link itself does
        # not repeat it.
        nxt="/rest/api/content?spaceKey=ENG&limit=50&cursor=x",
    )
    _Handler.payloads = {
        first_path: first,
        "/wiki/rest/api/content?spaceKey=ENG&limit=50&cursor=x": (
            200,
            {"results": [_content("2", "ENG", 1, "<p>b</p>")]},
        ),
    }

    found = list(pages(_config(site, [{"type": "space", "key": "ENG"}])))

    assert [p.path for p in found] == [
        "space-ENG/page-1.html",
        "space-ENG/page-2.html",
    ]


def test_scopes_union_without_pulling_a_page_twice(site: str) -> None:
    listing_path, listing = _listing(
        "ENG", [_content("1", "ENG", 7, "<p>Onboarding</p>")]
    )
    _Handler.payloads = {
        listing_path: listing,
        f"/wiki/rest/api/content/1?expand={EXPAND}": (
            200,
            _content("1", "ENG", 7, "<p>Onboarding</p>"),
        ),
    }

    found = list(
        pages(
            _config(
                site,
                [
                    {"type": "space", "key": "ENG"},
                    {"type": "page", "id": "1"},
                ],
            )
        )
    )

    assert [p.path for p in found] == ["space-ENG/page-1.html"]


def test_an_empty_scope_means_everything_visible(site: str) -> None:
    path, payload = _listing(None, [_content("9", "OPS", 2, "<p>x</p>")])
    _Handler.payloads = {path: payload}

    found = list(pages(_config(site, None)))

    assert [p.path for p in found] == ["space-OPS/page-9.html"]


def test_an_unsupported_selector_says_so(site: str) -> None:
    # the whole listing IS registered here, so a selector that silently fell
    # back to "everything" would succeed rather than fail — which is exactly
    # what a weaker assertion on the message let through.
    path, payload = _listing(None, [_content("9", "OPS", 2, "<p>x</p>")])
    _Handler.payloads = {path: payload}

    with pytest.raises(SyncError) as raised:
        list(pages(_config(site, [{"type": "label", "id": "x"}])))

    assert "unsupported" in str(raised.value)
    assert "label" in str(raised.value)


def test_refused_credentials_are_a_clean_domain_error(site: str) -> None:
    path, _payload = _listing("ENG", [])
    _Handler.payloads = {path: (401, {})}

    with pytest.raises(SyncError) as raised:
        list(pages(_config(site, [{"type": "space", "key": "ENG"}])))

    assert raised.value.code == "sync-error"
    assert "credentials" in str(raised.value)


def test_validation_checks_the_site_answers(site: str) -> None:
    _Handler.payloads = {"/wiki/rest/api/space?limit=1": (200, {})}

    validate_confluence(_config(site))

    _Handler.payloads = {"/wiki/rest/api/space?limit=1": (401, {})}
    with pytest.raises(ValidationFailed):
        validate_confluence(_config(site))


def test_the_instance_is_the_site_host() -> None:
    assert confluence_instance({"base_url": f"https://{SITE}/wiki"}) == SITE


def test_a_page_that_left_the_scope_leaves_the_cache(
    site: str, tmp_path: Path
) -> None:
    # the sync REPLACES the cache: a stale file would be reported as present
    # by every later diff, for ever.
    both_path, both = _listing(
        "ENG",
        [
            _content("1", "ENG", 1, "<p>a</p>"),
            _content("2", "ENG", 1, "<p>b</p>"),
        ],
    )
    _Handler.payloads = {both_path: both}
    cache = tmp_path / "cache"
    confluence_sync(_config(site, [{"type": "space", "key": "ENG"}]), cache, 5)
    assert (cache / "space-ENG/page-2.html").exists()

    one_path, one = _listing("ENG", [_content("1", "ENG", 1, "<p>a</p>")])
    _Handler.payloads = {one_path: one}
    confluence_sync(_config(site, [{"type": "space", "key": "ENG"}]), cache, 5)

    assert (cache / "space-ENG/page-1.html").exists()
    assert not (cache / "space-ENG/page-2.html").exists()


def test_split_addresses_each_page_at_its_own_version(
    site: str, tmp_path: Path
) -> None:
    path, payload = _listing(
        "ENG",
        [
            _content("1", "ENG", 7, "<p>Onboarding, at length.</p>"),
            _content("2", "ENG", 3, "<p>Deploys, at length.</p>"),
        ],
    )
    _Handler.payloads = {path: payload}
    config = _config(site, [{"type": "space", "key": "ENG"}])

    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn:
        registry_store.insert(
            conn, "sources", "wiki", json.dumps(config), None, "t"
        )
    context = JobContext(database, None, tmp_path / "cache")
    job = Job(
        id="j1",
        parent_id=None,
        tree=None,
        op="sync",
        scope={"name": "wiki"},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )

    sync(job, context)
    split_source(job, context)

    with database.connect() as conn:
        uris = sorted(
            str(r["uri"])
            for r in conn.execute(
                "SELECT uri FROM sections WHERE source = 'wiki'"
            ).fetchall()
        )
        types = {
            str(r["source_type"])
            for r in conn.execute(
                "SELECT DISTINCT source_type FROM sections WHERE source='wiki'"
            ).fetchall()
        }
    database.close()

    host = site.split("//", 1)[1].split("/", 1)[0]
    assert uris == [
        f"confluence://{host}/space-ENG/page-1.html@7",
        f"confluence://{host}/space-ENG/page-2.html@3",
    ]
    assert types == {"confluence"}
