"""#148: a bitbucket-workspace source discovers a workspace's repos.

What differs from #147 is the enumeration and only the enumeration, so that is
what these pin: `next`-link pagination (bitbucket carries the next URL in the
body rather than counting pages) and picking the https clone link out of the
several a repo advertises. The cloning, the globs, the per-repo versions and
the addresses are `discovery`'s, already pinned by #147's tests.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import pytest

from hrono.db.database import Database
from hrono.ingest import SyncError
from hrono.ingest.bitbucket import (
    API,
    bitbucket_instance,
    bitbucket_sync,
    repos,
    validate_bitbucket_workspace,
)
from hrono.ingest.split_op import split_source
from hrono.ingest.sync import sync
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.registry import store as registry_store
from hrono.registry.descriptor import ValidationFailed
from tests.stub_server import serving

WORKSPACE = "acme"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "PATH": "/usr/bin:/bin:/usr/local/bin",
}


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True,
        capture_output=True,
        text=True,
        env=GIT_ENV,
    ).stdout.strip()


def _repo(root: Path, name: str, files: dict[str, str]) -> str:
    path = root / name
    path.mkdir(parents=True)
    for rel, body in files.items():
        target = path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    _git(path, "init", "-q")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "first")
    return _git(path, "rev-parse", "HEAD")


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
def api() -> Iterator[str]:
    _Handler.payloads = {}
    _Handler.seen = []
    with serving(_Handler) as base:
        yield base


def _entry(name: str, root: Path) -> dict[str, object]:
    return {
        "slug": name,
        "links": {
            "clone": [
                {"name": "ssh", "href": f"git@bitbucket.org:acme/{name}.git"},
                {"name": "https", "href": str(root / name)},
            ]
        },
    }


def _fetch_through(base: str):
    from hrono.ingest.api import get_json

    def fetch(url: str, headers: dict[str, str], timeout: float):
        return get_json(url.replace(API, base), headers, timeout)

    return fetch


def test_enumeration_follows_the_next_link(api: str, tmp_path: Path) -> None:
    first = f"/repositories/{WORKSPACE}?pagelen=100"
    second = f"/repositories/{WORKSPACE}?pagelen=100&page=2"
    _Handler.payloads = {
        first: (
            200,
            {
                "values": [_entry("alpha", tmp_path)],
                "next": f"{API}{second}",
            },
        ),
        second: (200, {"values": [_entry("beta", tmp_path)]}),
    }

    found = repos({"name": "s", "owner": WORKSPACE}, fetch=_fetch_through(api))

    assert [name for name, _url in found] == ["alpha", "beta"]
    # followed the server's own url, rather than guessing a page number
    assert _Handler.seen == [first, second]


def test_the_https_clone_link_is_the_one_used(api: str, tmp_path: Path) -> None:
    # a token authenticates over https as x-token-auth; the ssh link would
    # need a key git may not have.
    _Handler.payloads = {
        f"/repositories/{WORKSPACE}?pagelen=100": (
            200,
            {"values": [_entry("alpha", tmp_path)]},
        )
    }

    found = repos({"name": "s", "owner": WORKSPACE}, fetch=_fetch_through(api))

    assert found == (("alpha", str(tmp_path / "alpha")),)


def test_an_entry_without_an_https_link_is_skipped(
    api: str, tmp_path: Path
) -> None:
    ssh_only = {
        "slug": "alpha",
        "links": {"clone": [{"name": "ssh", "href": "git@bitbucket.org:x"}]},
    }
    _Handler.payloads = {
        f"/repositories/{WORKSPACE}?pagelen=100": (
            200,
            {"values": [ssh_only, _entry("beta", tmp_path)]},
        )
    }

    found = repos({"name": "s", "owner": WORKSPACE}, fetch=_fetch_through(api))

    assert [name for name, _url in found] == ["beta"]


def test_an_unknown_workspace_is_a_clean_domain_error(api: str) -> None:
    with pytest.raises(SyncError) as raised:
        repos({"name": "s", "owner": "ghost"}, fetch=_fetch_through(api))

    assert "ghost" in str(raised.value)
    assert raised.value.code == "sync-error"


def test_validation_rejects_a_workspace_that_does_not_resolve(
    api: str,
) -> None:
    _Handler.payloads = {f"/workspaces/{WORKSPACE}": (200, {"slug": "acme"})}
    fetch = _fetch_through(api)

    validate_bitbucket_workspace({"owner": WORKSPACE}, None, fetch=fetch)

    with pytest.raises(ValidationFailed):
        validate_bitbucket_workspace({"owner": "ghost"}, None, fetch=fetch)


def test_the_instance_is_the_workspace_root(tmp_path: Path) -> None:
    assert (
        bitbucket_instance({"owner": WORKSPACE}, tmp_path)
        == "bitbucket.org/acme"
    )


def test_split_addresses_a_discovered_repo_as_git(
    api: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hrono.ingest import bitbucket

    origins = tmp_path / "origins"
    origins.mkdir()
    head = _repo(origins, "alpha", {"readme.md": "# Alpha\n\nfirst\n"})
    _Handler.payloads = {
        f"/repositories/{WORKSPACE}?pagelen=100": (
            200,
            {"values": [_entry("alpha", origins)]},
        )
    }
    monkeypatch.setattr(bitbucket, "get_json", _fetch_through(api))

    database = Database.at(tmp_path / "hrono.db")
    config = {
        "name": "acme-bb",
        "type": "bitbucket-workspace",
        "owner": WORKSPACE,
        "auth": {"method": "none"},
    }
    with database.connect() as conn:
        registry_store.insert(
            conn, "sources", "acme-bb", json.dumps(config), None, "t"
        )
    context = JobContext(database, None, tmp_path / "cache")
    job = Job(
        id="j1",
        parent_id=None,
        tree=None,
        op="sync",
        scope={"name": "acme-bb"},
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
                "SELECT uri FROM sections WHERE source = 'acme-bb'"
            ).fetchall()
        ]
    database.close()

    assert uris == [f"git://bitbucket.org/{WORKSPACE}/alpha/readme.md@{head}"]


def test_the_sync_writes_one_version_for_the_source(
    api: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hrono.ingest import bitbucket

    origins = tmp_path / "origins"
    origins.mkdir()
    head = _repo(origins, "alpha", {"readme.md": "# Alpha\n"})
    _Handler.payloads = {
        f"/repositories/{WORKSPACE}?pagelen=100": (
            200,
            {"values": [_entry("alpha", origins)]},
        )
    }
    monkeypatch.setattr(bitbucket, "get_json", _fetch_through(api))

    version = bitbucket_sync(
        {"name": "acme-bb", "owner": WORKSPACE, "auth": {"method": "none"}},
        tmp_path / "cache",
        60.0,
    )

    assert version != head  # a digest over the map, not a commit
    assert len(version) == 64
