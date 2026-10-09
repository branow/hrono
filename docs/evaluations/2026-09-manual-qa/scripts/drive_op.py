"""Run a registered op in-process, with the server stopped.

Needed for two reasons found during this run:
  * no HTTP or CLI trigger exists for any op except `maintain` (F9)
  * enqueuing a row from a second process wedges the running server (F23) and
    kills its worker thread (F24), so the queue cannot be used from outside

With the server stopped this process is the only writer, so the ops run under
exactly the code path the worker would use (same OPS registry, same JobContext),
and the outcome is recorded in `jobs` for the audit trail.

Usage:
  python drive_op.py <db> <key_file> <op> [tree] [scope_json]
"""

from __future__ import annotations

import json
import sys
import traceback
import uuid
from datetime import UTC, datetime

from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import load_key, reconcile
from hrono.db.database import Database, open_database
from hrono.jobs import store
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from pathlib import Path

import hrono.cluster.levels  # noqa: F401
import hrono.cluster.monitor  # noqa: F401
import hrono.cluster.op  # noqa: F401
import hrono.cluster.repair  # noqa: F401
import hrono.embed.op  # noqa: F401
import hrono.ingest.split_op  # noqa: F401
import hrono.ingest.sync  # noqa: F401
import hrono.summarize.brief  # noqa: F401
import hrono.summarize.brief_upper  # noqa: F401
import hrono.summarize.build_tree  # noqa: F401
import hrono.summarize.condense  # noqa: F401
import hrono.summarize.propagate  # noqa: F401
import hrono.tree.maintain  # noqa: F401
import hrono.tree.settle  # noqa: F401
import hrono.tree.update  # noqa: F401


def main() -> int:
    db_path, key_file, op = sys.argv[1], sys.argv[2], sys.argv[3]
    tree = sys.argv[4] if len(sys.argv) > 4 else "default"
    scope = json.loads(sys.argv[5]) if len(sys.argv) > 5 else {}

    key = load_key(Path(key_file), None)
    conn = open_database(Path(db_path))
    record = reconcile(conn, key)
    database = Database(conn)
    context = JobContext(database, Cipher.from_key(key, record.key_id))

    now = datetime.now(UTC).isoformat()
    job_id = f"job_{uuid.uuid4().hex}"
    with database.connect() as c, c:
        store.insert(c, job_id, None, tree, op, json.dumps(scope), now)
        store.set_status(c, job_id, "running", None, now)

    job = Job(
        id=job_id,
        parent_id=None,
        tree=tree,
        op=op,
        scope=scope,
        status="running",
        error=None,
        created_at=now,
        updated_at=now,
    )

    handler = OPS.get(op)
    if handler is None:
        print(f"unknown op: {op} (registered: {sorted(OPS)})")
        return 2

    started = datetime.now(UTC)
    status, error = "succeeded", None
    try:
        handler(job, context)
    except Exception as exc:  # noqa: BLE001 - the point is to report anything
        status, error = "failed", f"{type(exc).__name__}: {exc}"
        traceback.print_exc()
    finally:
        elapsed = (datetime.now(UTC) - started).total_seconds()
        with database.connect() as c, c:
            store.set_status(
                c, job_id, status, error, datetime.now(UTC).isoformat()
            )
        conn.close()
    print(f"{op} -> {status} in {elapsed:.1f}s  job={job_id}")
    if error:
        print(f"  error: {error}")
    return 0 if status == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
