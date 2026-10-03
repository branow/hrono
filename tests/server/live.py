"""A real server on a real port with a seeded database, for a real browser.

The dashboard's layout defects (#215) are properties of rendered pixels, so a
TestClient reading HTML cannot see them. This starts the production app under
uvicorn and hands a browser its address and an admin cookie.
"""

from __future__ import annotations

import json
import socket
import sqlite3
import subprocess
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
from hrono.summarize import briefs

KEY = Fernet.generate_key()
TREE = "default"


@dataclass(frozen=True)
class Live:
    base: str
    token: str
    repo: Path
    db_path: Path

    def write(self, sql: str, params: tuple = ()) -> None:
        """A write from outside the server, as another process would make it."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        try:
            with conn:
                conn.execute(sql, params)
        finally:
            conn.close()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repo(path: Path) -> tuple[Path, str]:
    """A real repository with one commit; returns it and that commit."""
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    (path / "a.md").write_text("one\n")
    _git(path, "add", ".")
    _git(
        path,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "commit",
        "-q",
        "-m",
        "one",
    )
    return path, _git(path, "rev-parse", "HEAD")


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


def _seed(conn: sqlite3.Connection, repo: Path, commit: str) -> None:
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
            "UPDATE jobs SET status = 'succeeded', result = '{}' "
            "WHERE id = 'done-1'"
        )
        conn.execute(
            "INSERT INTO source_state (source, version, synced_at) "
            "VALUES ('docs', ?, '2026-10-03T10:00:00+00:00')",
            (commit,),
        )


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def live_server(tmp_path: Path) -> Iterator[Live]:
    repo, commit = _repo(tmp_path / "repo")
    db_path = tmp_path / "hrono.db"
    conn = open_database(db_path)
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    _seed(conn, repo, commit)
    conn.close()
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(db_path=db_path, master_key=KEY),
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
