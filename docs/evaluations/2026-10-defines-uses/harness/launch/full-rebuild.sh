#!/bin/zsh
cd /Users/orest/repos/hrono/docs/evaluations/2026-10-defines-uses/harness
export HRONO_LLM_CONCURRENCY=6
L=~/hrono-eval/full-rebuild.log
for i in 0 1 2 3 4 5; do
  echo "run $i $(date)" >> $L
  uv run --extra claude-code --extra embed python subtree_v9.py full >> $L 2>&1 && { echo "DONE $(date)" >> $L; exit 0; }
done
echo "FAILED $(date)" >> $L
