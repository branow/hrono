"""A real server on a real port with a seeded database, for a real browser.

The dashboard's layout defects are properties of rendered pixels, so a
TestClient reading HTML cannot see them. This starts the production app under
uvicorn and hands a browser its address and an admin cookie.
"""

from __future__ import annotations

import json
import socket
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import uvicorn
from cryptography.fernet import Fernet

from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.jobs import store as job_store
from hrono.registry import store as registry_store
from hrono.server.app import create_app
from hrono.server.freshness import Heads
from hrono.summarize import briefs
from tests.server.repo import commit, head_of, make_repo

KEY = Fernet.generate_key()
# a run the worker's reclaimer will believe is held by a live worker
FAR_FUTURE = "2999-01-01T00:00:00+00:00"
TREE = "default"


@dataclass(frozen=True)
class Live:
    base: str
    token: str
    repo: Path
    db_path: Path

    def advance(self) -> str:
        """Move the source's remote on by one commit; return the new one."""
        return commit(self.repo, "another")

    def run_fanout(self, total: int) -> str:
        """A run in progress: a parent and `total` pieces, all running."""
        stamp = "2026-10-03T11:00:00+00:00"
        self.write(
            "INSERT INTO jobs (id, tree, op, scope, status, created_at, "
            "updated_at) VALUES ('going', 'default', 'sync', '{}', "
            "'pending', ?, ?)",
            (stamp, stamp),
        )
        for index in range(total):
            self.write(
                "INSERT INTO jobs (id, parent_id, tree, op, scope, status, "
                "created_at, updated_at, heartbeat) VALUES (?, 'going', "
                "'default', 'sync', '{}', 'running', ?, ?, ?)",
                (f"piece-{index}", stamp, stamp, FAR_FUTURE),
            )
        return "going"

    def finish_piece(self, index: int) -> None:
        self.write(
            "UPDATE jobs SET status = 'succeeded' WHERE id = ?",
            (f"piece-{index}",),
        )

    def write(self, sql: str, params: tuple = ()) -> None:
        """A write from outside the server, as another process would make it."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        try:
            with conn:
                conn.execute(sql, params)
        finally:
            conn.close()


def _repo(path: Path) -> tuple[Path, str]:
    return make_repo(path), head_of(path)


def _section(conn: sqlite3.Connection, path: str, body: bytes) -> int:
    digest = content_hash(body)
    istore.upsert_content(conn, digest, body)
    return istore.insert_section(
        conn,
        source="docs",
        address=Address("git", "ex/docs", path, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )


def _seed(
    conn: sqlite3.Connection, repo: Path, commit: str, built: bool
) -> None:
    if built:
        _build(conn)
    _register(conn, repo, commit, built)


def _build(conn: sqlite3.Connection) -> None:
    with conn:
        sections = [
            (
                _section(conn, f"docs/{i}.md", f"body {i}\n".encode()),
                False,
                None,
            )
            for i in range(3)
        ]
        leaf = cluster_store.add_leaf_node(conn, TREE, sections)
        briefs.upsert(
            conn,
            leaf,
            "Signing and serialization.\nThe modules that sign payloads.",
            model_name="scribe-9",
            prompt_name="brief",
            prompt_hash="h",
            member_signature="sig",
            input_tokens=10,
            output_tokens=5,
        )
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 1, 0, 't')",
            (TREE,),
        )
        parent = int(conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0])
        cluster_store.add_child(
            conn, parent, leaf, attached=False, similarity=None
        )


def _register(
    conn: sqlite3.Connection, repo: Path, commit: str, ran: bool
) -> None:
    registry_store.insert(
        conn,
        "sources",
        "docs",
        json.dumps(
            {
                "name": "docs",
                "type": "git",
                "url": str(repo),
                "auth": {"method": "none"},
            }
        ),
        None,
        "t",
    )
    if not ran:
        return
    job_store.insert(
        conn,
        "done-1",
        None,
        TREE,
        "sync-tree",
        "{}",
        "2026-10-03T10:00:00+00:00",
    )
    with conn:
        conn.execute(
            "UPDATE jobs SET status = 'succeeded', result = '{}', "
            "started_by = 'a-person-with-a-rather-long-name' "
            "WHERE id = 'done-1'"
        )
        conn.execute(
            "INSERT INTO source_state (source, version, synced_at) "
            "VALUES ('docs', ?, '2026-10-03T10:00:00+00:00')",
            (commit,),
        )
        for provider in ("anthropic", "claude-code"):
            conn.execute(
                "INSERT INTO llm_calls (job_id, run_id, started_by, model, "
                "role, provider, upstream_model, input_tokens, "
                "output_tokens, cache_read_tokens, cache_creation_tokens, "
                "duration_ms, ok, created_at) VALUES ('done-1', 'done-1', "
                "'a-person-with-a-rather-long-name', "
                "'a-long-model-name-that-stresses-the-table-layout', "
                "'brief', ?, 'claude-sonnet-5-20260101', 120000, 3400, 900, "
                "0, 65000, 1, '2026-10-03T10:01:00+00:00')",
                (provider,),
            )


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def live_server(tmp_path: Path, built: bool = True) -> Iterator[Live]:
    """`built=False` is a first run: a source, and no topics or runs yet."""
    repo, commit = _repo(tmp_path / "repo")
    db_path = tmp_path / "hrono.db"
    conn = open_database(db_path)
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    _seed(conn, repo, commit, built)
    conn.close()
    port = _free_port()
    app = create_app(db_path=db_path, master_key=KEY)
    # the remote is asked every time, so a commit made mid-test is seen
    app.state.heads = Heads(fresh_for=0.0)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.02)
    try:
        yield Live(f"http://127.0.0.1:{port}", token, repo, db_path)
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        assert not thread.is_alive(), "the server did not shut down"
