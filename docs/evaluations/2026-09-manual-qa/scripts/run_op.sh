#!/usr/bin/env bash
# Enqueue an op and block until the worker finishes it, printing the job row.
#   ./run_op.sh update            # tree defaults to "default"
#   ./run_op.sh propagate default '{}'
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="$ROOT/run/.hrono/hrono.db"
OP="$1"
TREE="${2:-default}"
SCOPE="${3:-\{\}}"
JOB=$(uv run --project "$(git rev-parse --show-toplevel)" python "$ROOT/scripts/enqueue.py" \
  "$DB" "$OP" "$TREE" "$SCOPE")
echo "enqueued $OP as $JOB at $(date -u +%H:%M:%SZ)"
while true; do
  ROW=$(uv run --project "$(git rev-parse --show-toplevel)" python - "$DB" "$JOB" <<'PY'
import sqlite3, sys
c = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
r = c.execute(
    "select status, coalesce(error,'') from jobs where id=?", (sys.argv[2],)
).fetchone()
print(f"{r[0]}\t{r[1]}")
PY
)
  STATUS="${ROW%%	*}"
  case "$STATUS" in
    succeeded|failed|canceled)
      echo "$OP -> $ROW  (at $(date -u +%H:%M:%SZ))"
      { echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) op=$OP job=$JOB -> $ROW"; } \
        >> "$ROOT/logs/ops.log"
      exit 0
      ;;
  esac
  sleep 3
done
