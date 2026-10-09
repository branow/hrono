"""Enqueue any registered op as a job row, for ops with no HTTP trigger.

Only `POST /trees/{name}/maintain` exists in the API, so update / propagate /
monitor / repair / settle / individual ops are unreachable from outside. This
inserts a pending job row into the running server's SQLite file; the server's
worker claims and runs it through the real op registry (WAL + busy_timeout make
the cross-process insert safe).

Usage: python enqueue.py <db_path> <op> [tree] [scope_json]
"""

from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from datetime import UTC, datetime


def main() -> None:
    db_path = sys.argv[1]
    op = sys.argv[2]
    tree = sys.argv[3] if len(sys.argv) > 3 else "default"
    scope = sys.argv[4] if len(sys.argv) > 4 else "{}"
    job_id = f"job_{uuid.uuid4().hex}"
    now = datetime.now(UTC).isoformat()
    conn = sqlite3.connect(db_path, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    with conn:
        conn.execute(
            "INSERT INTO jobs(id, parent_id, tree, op, scope, status, error, "
            "created_at, updated_at) VALUES (?,?,?,?,?,'pending',NULL,?,?)",
            (job_id, None, tree, op, json.dumps(json.loads(scope)), now, now),
        )
    conn.close()
    print(job_id)


if __name__ == "__main__":
    main()
