#!/usr/bin/env bash
# Logged curl helper. Every call and its response land in logs/api.log so the
# whole run is reproducible and auditable.
#   ./api.sh GET /sources
#   ./api.sh POST /models '{"name":"..."}'
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${HRONO_BASE:-http://127.0.0.1:8299}"
TOKEN="$(cat "$ROOT/run/admin.token")"
METHOD="$1"
PATH_="$2"
BODY="${3:-}"
LOG="$ROOT/logs/api.log"
{
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ) $METHOD $PATH_"
  [ -n "$BODY" ] && echo "--- request"  && echo "$BODY"
} >> "$LOG"
if [ -n "$BODY" ]; then
  OUT=$(curl -sS -X "$METHOD" "$BASE$PATH_" \
    -H "Authorization: Bearer $TOKEN" \
    -H 'content-type: application/json' -d "$BODY" -w '\n<<HTTP %{http_code}>>')
else
  OUT=$(curl -sS -X "$METHOD" "$BASE$PATH_" \
    -H "Authorization: Bearer $TOKEN" -w '\n<<HTTP %{http_code}>>')
fi
{
  echo "--- response"
  echo "$OUT"
  echo
} >> "$LOG"
echo "$OUT"
