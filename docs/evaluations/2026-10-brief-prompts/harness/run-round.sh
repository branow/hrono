#!/bin/sh
# Brief and judge leaves with the given prompts: run-round.sh "LEAVES" PROMPT...
# Needs CACHE; condensations use purpose-decisions.
set -e
leaves=$1; shift
A=../../2026-10-cluster-formula/data/detail/cond6-h4+g/assignment.npz
export CONDENSE_PROMPT=purpose-decisions JUDGE_RUNS=2
export JUDGE_NOISE=today,decisions,core,$(echo "$@" | tr ' ' ',')
for L in $leaves; do
  echo "== leaf $L"
  uv run python pilot.py ~/hrono-eval/db/hrono.db $A $L ../data/condense-decisions "$CACHE" "$@" | grep calls
  uv run python judge.py ~/hrono-eval/db/hrono.db $A $L ../data/condense-decisions "$CACHE" | sed -n '3,30p' | grep '^| `'
done
