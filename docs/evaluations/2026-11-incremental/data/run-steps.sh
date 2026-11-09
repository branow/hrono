#!/bin/sh
# E1: for each planned step, move the pin, sync, keep the job report and a db copy.
# Usage: ./run-steps.sh <first-step> <last-step>
set -e
cd "$(dirname "$0")"
plan=/Users/orest/repos/hrono/docs/evaluations/2026-11-incremental/steps-plan.tsv
for n in $(seq "$1" "$2"); do
  nn=$(printf %02d "$n")
  [ -f "db/step-$nn.db" ] && continue
  commit=$(awk -F'\t' -v s="$n" '$1==s {print $2}' "$plan")
  git -C pin.git update-ref refs/heads/master "$commit"
  job=$(./h tree sync streamlink | sed -n 's/.*job \(job_[0-9a-f]*\).*/\1/p' | head -1)
  echo "step $nn $commit $job $(date -u +%FT%TZ)" >> steps.log
  ./h jobs watch "$job" > "jobs/step-$nn.watch" 2>&1 || true
  ./h jobs get "$job" > "jobs/step-$nn.txt" 2>&1 || true
  python3 -c "import sys;t=open(sys.argv[1]).read();print(t[t.index('{'):])" "jobs/step-$nn.txt" > "jobs/step-$nn.json"
  sqlite3 db/hrono.db ".backup db/step-$nn.db"
  echo "done $nn $(date -u +%FT%TZ) $(head -1 jobs/step-$nn.txt)" >> steps.log
done
