"""Drive settle with force=True to exercise the warm-reconcile path itself."""
import sys, traceback
from pathlib import Path
from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import load_key, reconcile
from hrono.db.database import Database, open_database
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.tree.settle import settle

key = load_key(Path(sys.argv[2]), None)
conn = open_database(Path(sys.argv[1]))
rec = reconcile(conn, key)
db = Database(conn)
ctx = JobContext(db, Cipher.from_key(key, rec.key_id))
job = Job(id="force-settle", parent_id=None, tree="default", op="settle",
          scope={}, status="running", error=None, created_at="t", updated_at="t")
try:
    settle(job, ctx, force=True)
    print("settle(force=True) -> succeeded")
except Exception as exc:
    print(f"settle(force=True) -> FAILED: {type(exc).__name__}: {exc}")
    traceback.print_exc()
finally:
    conn.close()
