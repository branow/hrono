"""#150: a notion source ingests the pages shared with its integration.

Notion's difference from confluence is structural: there is no document to
fetch, only a tree of blocks, so the renderer is where the content is won or
lost. These pin the renderer, the search-based "everything this token can see",
cursor pagination, and the rule that the workspace in an address comes from the
TOKEN rather than from config.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import pytest

from hrono.db.database import Database
from hrono.ingest import SyncError
from hrono.ingest.notion import (
    notion_instance,
    notion_sync,
    pages,
    render,
    validate_notion,
    workspace,
)
from hrono.ingest.split_op import split_source
from hrono.ingest.sync import sync
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.registry import store as registry_store
from hrono.registry.descriptor import ValidationFailed
from tests.stub_server import serving

PLACEHOLDER = "n" * 12  # stands in for the integration credential
WORKSPACE = "Acme HQ"


class _Handler(BaseHTTPRequestHandler):
    gets: dict[str, tuple[int, object]] = {}
    posts: dict[str, list[tuple[int, object]]] = {}
    seen: list[str] = []

    def _respond(self, status: int, body: object) -> None:
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's name
        _Handler.seen.append(f"GET {self.path}")
        status, body = _Handler.gets.get(self.path, (404, {}))
        self._respond(status, body)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's name
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        _Handler.seen.append(f"POST {self.path}")
        queue = _Handler.posts.get(self.path)
        if not queue:
            self._respond(404, {})
            return
        status, body = queue.pop(0) if len(queue) > 1 else queue[0]
        self._respond(status, body)

    def log_message(self, *args: object) -> None:
        return


@pytest.fixture
def notion() -> Iterator[str]:
    _Handler.gets = {}
    _Handler.posts = {}
    _Handler.seen = []
    with serving(_Handler) as base:
        yield base + "/v1"


def _through(base: str):
    """The real HTTP calls, pointed at the stub instead of api.notion.com."""
    from hrono.ingest.api import get_json, post_json
    from hrono.ingest.notion import API

    def get(url: str, headers: dict[str, str], timeout: float):
        return get_json(url.replace(API, base), headers, timeout)

    def post(url: str, headers: dict[str, str], body: dict, timeout: float):
        return post_json(url.replace(API, base), headers, body, timeout)

    return get, post


def _text(value: str) -> dict:
    return {"rich_text": [{"plain_text": value}]}


def _block(kind: str, value: str, children: bool = False) -> dict:
    return {
        "id": f"b-{value[:4]}",
        "type": kind,
        kind: _text(value),
        "has_children": children,
    }


def _config() -> dict:
    return {
        "name": "product",
        "type": "notion",
        "auth": {"method": "token", "token": PLACEHOLDER},
    }


def test_the_renderer_shapes_the_blocks_it_knows() -> None:
    body = render(
        [
            _block("heading_1", "Onboarding"),
            _block("paragraph", "Read this first."),
            _block("bulleted_list_item", "Install the toolchain"),
            _block("numbered_list_item", "Then run the tests"),
            _block("to_do", "Ask for access"),
            _block("quote", "It is a tag plus a button."),
            _block("code", "make test"),
        ]
    )

    assert body == (
        "# Onboarding\n\n"
        "Read this first.\n\n"
        "- Install the toolchain\n\n"
        "1. Then run the tests\n\n"
        "- [ ] Ask for access\n\n"
        "> It is a tag plus a button.\n\n"
        "    make test\n"
    )


def test_an_unknown_block_contributes_its_text_rather_than_nothing() -> None:
    # notion adds block types; losing a page's content to one is worse than
    # rendering it unstyled.
    body = render([_block("callout", "Mind the gap"), {"type": "divider"}])

    assert body == "Mind the gap\n"


def test_everything_shared_with_the_token_is_the_default_scope(
    notion: str,
) -> None:
    get, post = _through(notion)
    _Handler.posts = {
        "/v1/search": [
            (
                200,
                {
                    "results": [
                        {"id": "p1", "last_edited_time": "2026-09-01T00:00Z"}
                    ]
                },
            )
        ]
    }
    _Handler.gets = {
        "/v1/blocks/p1/children?page_size=100": (
            200,
            {"results": [_block("paragraph", "hello")]},
        )
    }

    found = list(pages(_config(), get=get, post=post))

    assert [p.path for p in found] == ["page-p1.md"]
    assert found[0].version == "2026-09-01T00:00Z"
    assert found[0].body == b"hello\n"


def test_search_follows_its_cursor(notion: str) -> None:
    get, post = _through(notion)
    _Handler.posts = {
        "/v1/search": [
            (
                200,
                {
                    "results": [{"id": "p1", "last_edited_time": "t1"}],
                    "has_more": True,
                    "next_cursor": "c2",
                },
            ),
            (200, {"results": [{"id": "p2", "last_edited_time": "t2"}]}),
        ]
    }
    _Handler.gets = {
        "/v1/blocks/p1/children?page_size=100": (
            200,
            {"results": [_block("paragraph", "one")]},
        ),
        "/v1/blocks/p2/children?page_size=100": (
            200,
            {"results": [_block("paragraph", "two")]},
        ),
    }

    found = list(pages(_config(), get=get, post=post))

    assert [p.path for p in found] == ["page-p1.md", "page-p2.md"]


def test_nested_blocks_are_followed(notion: str) -> None:
    get, post = _through(notion)
    parent = _block("bulleted_list_item", "Parent", children=True)
    _Handler.posts = {
        "/v1/search": [
            (200, {"results": [{"id": "p1", "last_edited_time": "t"}]})
        ]
    }
    _Handler.gets = {
        "/v1/blocks/p1/children?page_size=100": (200, {"results": [parent]}),
        f"/v1/blocks/{parent['id']}/children?page_size=100": (
            200,
            {"results": [_block("paragraph", "Child")]},
        ),
    }

    found = list(pages(_config(), get=get, post=post))

    assert found[0].body == b"- Parent\n\nChild\n"


def test_an_unsupported_selector_says_so(notion: str) -> None:
    get, post = _through(notion)
    _Handler.posts = {
        "/v1/search": [
            (200, {"results": [{"id": "p1", "last_edited_time": "t"}]})
        ]
    }

    with pytest.raises(SyncError) as raised:
        list(
            pages(
                {**_config(), "scope": [{"type": "block", "id": "x"}]},
                get=get,
                post=post,
            )
        )

    assert "unsupported" in str(raised.value)


def test_refused_credentials_are_a_clean_domain_error(notion: str) -> None:
    get, post = _through(notion)
    _Handler.posts = {"/v1/search": [(401, {})]}

    with pytest.raises(SyncError) as raised:
        list(pages(_config(), get=get, post=post))

    assert raised.value.code == "sync-error"
    assert "credentials" in str(raised.value)


def test_the_workspace_comes_from_the_token(notion: str) -> None:
    get, _post = _through(notion)
    _Handler.gets = {
        "/v1/users/me": (200, {"bot": {"workspace_name": WORKSPACE}})
    }

    assert workspace(_config(), get=get) == WORKSPACE


def test_the_instance_is_read_back_from_the_sync(
    notion: str, tmp_path: Path
) -> None:
    # an address must not depend on a live call: after one sync the source
    # keeps addressing its pages the same way, offline included.
    get, post = _through(notion)
    _Handler.gets = {
        "/v1/users/me": (200, {"bot": {"workspace_name": WORKSPACE}}),
        "/v1/blocks/p1/children?page_size=100": (
            200,
            {"results": [_block("paragraph", "hello")]},
        ),
    }
    _Handler.posts = {
        "/v1/search": [
            (200, {"results": [{"id": "p1", "last_edited_time": "t"}]})
        ]
    }
    cache = tmp_path / "cache"

    notion_sync(_config(), cache, 5.0, get=get, post=post)

    # a workspace NAME is free text and an instance lands verbatim in a URI:
    # "Acme HQ" must not produce `notion://Acme HQ/...`, which is not a URI.
    assert " " not in notion_instance(_config(), cache)
    assert notion_instance(_config(), cache) == "Acme%20HQ"
    with pytest.raises(SyncError):
        notion_instance(_config(), tmp_path / "never-synced")


def test_validation_rejects_a_token_that_does_not_authenticate(
    notion: str,
) -> None:
    get, _post = _through(notion)
    _Handler.gets = {"/v1/users/me": (200, {"bot": {}})}

    validate_notion(_config(), None, get=get)

    _Handler.gets = {"/v1/users/me": (401, {})}
    with pytest.raises(ValidationFailed):
        validate_notion(_config(), None, get=get)


def test_split_addresses_a_page_by_workspace_and_edited_time(
    notion: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hrono.ingest import notion as module

    get, post = _through(notion)
    monkeypatch.setattr(module, "get_json", get)
    monkeypatch.setattr(module, "post_json", post)
    _Handler.gets = {
        "/v1/users/me": (200, {"bot": {"workspace_name": WORKSPACE}}),
        "/v1/blocks/p1/children?page_size=100": (
            200,
            {"results": [_block("paragraph", "A page with some prose.")]},
        ),
    }
    _Handler.posts = {
        "/v1/search": [
            (
                200,
                {
                    "results": [
                        {"id": "p1", "last_edited_time": "2026-09-01T10:00Z"}
                    ]
                },
            )
        ]
    }

    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn:
        registry_store.insert(
            conn, "sources", "product", json.dumps(_config()), None, "t"
        )
    context = JobContext(database, None, tmp_path / "cache")
    job = Job(
        id="j1",
        parent_id=None,
        tree=None,
        op="sync",
        scope={"name": "product"},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )

    sync(job, context)
    split_source(job, context)

    with database.connect() as conn:
        uris = [
            str(r["uri"])
            for r in conn.execute(
                "SELECT uri FROM sections WHERE source = 'product'"
            ).fetchall()
        ]
    database.close()

    assert uris == ["notion://Acme%20HQ/page-p1.md@2026-09-01T10:00Z"]
