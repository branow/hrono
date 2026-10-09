"""A github-user source discovers an owner's repos and ingests them all.

The seam's payoff, measured: `github-user` is a model variant plus three table
entries, and no ingest engine changed to accept it. What these pin is the part
that is genuinely new — enumeration, the repo-name globs, and the rule that
each discovered repo keeps its OWN commit as the version of its files.

Enumeration runs against a real HTTP server on a real socket: a mocked
client object would prove the glob code and nothing about the request.
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
from hrono.ingest.discovery import unit as discovered_unit
from hrono.ingest.discovery import units as discovered_units
from hrono.ingest.github import (
    API,
    github_instance,
    github_sync,
    repos,
    validate_github_user,
)
from hrono.ingest.split_op import split_source
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.registry import store as registry_store
from hrono.registry.descriptor import ValidationFailed
from tests.stub_server import serving

OWNER = "acme"
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
    """A real HTTP server standing in for api.github.com."""
    _Handler.payloads = {}
    _Handler.seen = []
    with serving(_Handler) as base:
        yield base


def _page(names: list[str], root: Path) -> list[dict[str, str]]:
    return [{"name": name, "clone_url": str(root / name)} for name in names]


def _fetch_through(base: str):
    """The real HTTP GET, pointed at the stub instead of api.github.com."""
    from hrono.ingest.api import get_json

    def fetch(url: str, headers: dict[str, str], timeout: float):
        return get_json(url.replace(API, base), headers, timeout)

    return fetch


def test_enumeration_follows_pages_over_a_real_request(
    api: str, tmp_path: Path
) -> None:
    from hrono.ingest import github

    first = _page([f"r{i}" for i in range(github.PER_PAGE)], tmp_path)
    _Handler.payloads = {
        f"/users/{OWNER}/repos?per_page={github.PER_PAGE}&page=1": (
            200,
            first,
        ),
        f"/users/{OWNER}/repos?per_page={github.PER_PAGE}&page=2": (
            200,
            _page(["last"], tmp_path),
        ),
    }

    found = repos({"name": "s", "owner": OWNER}, fetch=_fetch_through(api))

    assert len(found) == github.PER_PAGE + 1  # the short page ended it
    assert ("last", str(tmp_path / "last")) in found
    assert len(_Handler.seen) == 2


def test_repo_name_globs_filter_what_is_discovered(
    api: str, tmp_path: Path
) -> None:
    from hrono.ingest import github

    _Handler.payloads = {
        f"/users/{OWNER}/repos?per_page={github.PER_PAGE}&page=1": (
            200,
            _page(["api", "api-archive", "docs", "web"], tmp_path),
        )
    }

    found = repos(
        {
            "name": "s",
            "owner": OWNER,
            "include": ["api*", "docs"],
            "exclude": ["*-archive"],
        },
        fetch=_fetch_through(api),
    )

    assert [name for name, _url in found] == ["api", "docs"]


def test_an_unknown_owner_is_a_clean_domain_error(
    api: str, tmp_path: Path
) -> None:
    with pytest.raises(SyncError) as raised:
        repos({"name": "s", "owner": "ghost"}, fetch=_fetch_through(api))

    assert "ghost" in str(raised.value)
    assert raised.value.code == "sync-error"  # its own domain code


def test_validation_rejects_an_owner_that_does_not_resolve(api: str) -> None:
    _Handler.payloads = {f"/users/{OWNER}": (200, {"login": OWNER})}
    fetch = _fetch_through(api)

    validate_github_user({"owner": OWNER}, None, fetch=fetch)  # no raise

    with pytest.raises(ValidationFailed):
        validate_github_user({"owner": "ghost"}, None, fetch=fetch)


def test_each_discovered_repo_keeps_its_own_commit(
    api: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the rule this type exists to get right: one source, many versions.
    from hrono.ingest import github

    origins = tmp_path / "origins"
    origins.mkdir()
    head_a = _repo(origins, "alpha", {"readme.md": "# Alpha\n\nfirst\n"})
    head_b = _repo(origins, "beta", {"docs/guide.md": "# Beta\n\nsecond\n"})
    _Handler.payloads = {
        f"/users/{OWNER}/repos?per_page={github.PER_PAGE}&page=1": (
            200,
            _page(["alpha", "beta"], origins),
        )
    }
    monkeypatch.setattr(github, "get_json", _fetch_through(api))

    config = {"name": "acme", "owner": OWNER, "auth": {"method": "none"}}
    cache = tmp_path / "cache" / "acme"
    version = github_sync(config, cache, 60.0)

    units = {u.path: u for u in discovered_units(config, cache)}
    assert set(units) == {"alpha/readme.md", "beta/docs/guide.md"}
    assert units["alpha/readme.md"].version == head_a
    assert units["beta/docs/guide.md"].version == head_b
    assert version not in (head_a, head_b)  # the source's own digest

    one = discovered_unit(config, cache, "beta/docs/guide.md")
    assert one.body == units["beta/docs/guide.md"].body
    assert one.version == head_b


def test_split_addresses_every_repo_as_its_own(
    api: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hrono.ingest import github

    origins = tmp_path / "origins"
    origins.mkdir()
    head_a = _repo(origins, "alpha", {"readme.md": "# Alpha\n\nfirst\n"})
    head_b = _repo(origins, "beta", {"docs/guide.md": "# Beta\n\nsecond\n"})
    _Handler.payloads = {
        f"/users/{OWNER}/repos?per_page={github.PER_PAGE}&page=1": (
            200,
            _page(["alpha", "beta"], origins),
        )
    }
    monkeypatch.setattr(github, "get_json", _fetch_through(api))

    database = Database.at(tmp_path / "hrono.db")
    config = {
        "name": "acme",
        "type": "github-user",
        "owner": OWNER,
        "auth": {"method": "none"},
    }
    with database.connect() as conn:
        registry_store.insert(
            conn, "sources", "acme", json.dumps(config), None, "t"
        )
    context = JobContext(database, None, tmp_path / "cache")
    job = Job(
        id="j1",
        parent_id=None,
        tree=None,
        op="sync",
        scope={"name": "acme"},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )
    from hrono.ingest.sync import sync

    sync(job, context)
    split_source(job, context)

    with database.connect() as conn:
        rows = {
            str(r["path"]): str(r["uri"])
            for r in conn.execute(
                "SELECT path, uri FROM sections WHERE source = 'acme'"
            ).fetchall()
        }
    database.close()

    # the spec's rule: discovery is how a repo was FOUND, not its address
    assert rows["alpha/readme.md"] == (
        f"git://github.com/{OWNER}/alpha/readme.md@{head_a}"
    )
    assert rows["beta/docs/guide.md"] == (
        f"git://github.com/{OWNER}/beta/docs/guide.md@{head_b}"
    )


def test_the_instance_is_the_owner_root(tmp_path: Path) -> None:
    assert github_instance({"owner": OWNER}, tmp_path) == f"github.com/{OWNER}"


def test_reading_before_a_sync_says_so(tmp_path: Path) -> None:
    with pytest.raises(SyncError) as raised:
        list(discovered_units({"owner": OWNER}, tmp_path / "never-synced"))

    assert "synced" in str(raised.value)


def test_an_update_addresses_a_changed_unit_the_same_way(
    api: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the half a full-split test cannot see: `update` re-stores only the
    # changed units, and if it addressed them as `github-user://` while the
    # split wrote `git://`, every unit of every discovered repo would look new
    # on the next diff — a full re-ingest, which is the one thing hrono
    # promises never to do.
    from hrono.ingest import github
    from hrono.ingest.diff import diff
    from hrono.ingest.readers import READERS
    from hrono.ingest.reconcile import reconcile

    origins = tmp_path / "origins"
    origins.mkdir()
    _repo(origins, "alpha", {"readme.md": "# Alpha\n\nfirst\n"})
    _Handler.payloads = {
        f"/users/{OWNER}/repos?per_page={github.PER_PAGE}&page=1": (
            200,
            _page(["alpha"], origins),
        )
    }
    monkeypatch.setattr(github, "get_json", _fetch_through(api))

    database = Database.at(tmp_path / "hrono.db")
    config = {
        "name": "acme",
        "type": "github-user",
        "owner": OWNER,
        "auth": {"method": "none"},
    }
    with database.connect() as conn:
        registry_store.insert(
            conn, "sources", "acme", json.dumps(config), None, "t"
        )
    context = JobContext(database, None, tmp_path / "cache")
    job = Job(
        id="j1",
        parent_id=None,
        tree=None,
        op="sync",
        scope={"name": "acme"},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )
    from hrono.ingest.sync import sync

    sync(job, context)
    split_source(job, context)

    (origins / "alpha" / "readme.md").write_text("# Alpha\n\nedited\n")
    _git(origins / "alpha", "commit", "-q", "-am", "second")
    head = _git(origins / "alpha", "rev-parse", "HEAD")
    sync(job, context)

    cache = context.cache_for("acme")
    reader = READERS["github-user"]
    with database.write() as conn:
        changes = diff(conn, "acme", reader, config, cache)
        assert [(c.path, c.status) for c in changes] == [
            ("alpha/readme.md", "changed")
        ]
        reconcile(
            conn,
            tree="default",
            source="acme",
            source_type=reader.addresses_as or "github-user",
            instance=reader.instance(config, cache),
            version="ignored",
            fetch=lambda path: reader.unit(config, cache, path),
            changes=changes,
        )

    with database.connect() as conn:
        uris = [
            str(r["uri"])
            for r in conn.execute(
                "SELECT uri FROM sections WHERE source = 'acme'"
            ).fetchall()
        ]
    database.close()

    assert uris == [f"git://github.com/{OWNER}/alpha/readme.md@{head}"]
