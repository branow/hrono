#!/bin/sh
# Replay history month by month: pin every mirror to the first of each month,
# run `hrono tree sync`, wait for it, and keep the job report and the ledger
# rows of that run under replay/<date>/.
# usage: replay.sh 2024-11-01 2024-12-01 ...
set -u
root="$(cd "$(dirname "$0")/.." && pwd)"
h="$root/bin/h"
db="$root/db/hrono.db"
for date in "$@"; do
  out="$root/replay/$date"
  mkdir -p "$out"
  "$root/bin/pin.sh" "$date" > "$out/pins.txt"
  start=$(date +%s)
  job=$("$h" tree sync bcreg 2>&1 | sed -n 's/.*job \(job_[0-9a-f]*\).*/\1/p' | head -1)
  if [ -z "$job" ]; then
    echo "$date: sync did not start" | tee "$out/error.txt"
    exit 1
  fi
  "$h" jobs watch "$job" > "$out/watch.txt" 2>&1
  code=$?
  end=$(date +%s)
  "$h" jobs get "$job" > "$out/job.txt" 2>&1
  sqlite3 -header "$db" \
    "select role, count(*) calls, sum(input_tokens) inp, \
     sum(output_tokens) outp, sum(duration_ms)/1000 secs \
     from llm_calls where run_id = '$job' group by role" > "$out/calls.txt"
  echo "$date job=$job exit=$code wall=$((end - start))s" | tee -a "$root/replay/summary.txt"
  [ "$code" -eq 0 ] || exit 1
done
