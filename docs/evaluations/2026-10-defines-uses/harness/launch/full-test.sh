#!/bin/zsh
# The untuned test: all 15 hard15 questions, hrono vs code only, 2 tries each.
H=/Users/orest/repos/hrono/docs/evaluations/2026-10-defines-uses/harness
cd $H
uv run python subtree_v9.py export > ~/hrono-eval/full-export.log 2>&1 || exit 1
qs=($(python3 -c "import json;print(' '.join(q['qid'] for q in json.load(open('$HOME/hrono-deep/data/hard15.json'))))"))
jobs_list=()
for q in $qs; do for t in a b; do
  jobs_list+=("plugin $q hrono-full$t@sonnet" "none $q code-full$t@sonnet")
done; done
printf '%s\n' $jobs_list | xargs -P 4 -L 1 zsh -c 'MAP=$0 EXPORT=export-bcreg-v9-L3 uv run --extra claude-code python agent_v2.py run $1 $2 > ~/hrono-eval/full-$2-$1.log 2>&1'
cd ~/hrono-deep && uv run --project /Users/orest/repos/hrono python harness/score.py hard15 hrono-fulla@sonnet hrono-fullb@sonnet code-fulla@sonnet code-fullb@sonnet > ~/hrono-eval/full-score.log 2>&1
echo "TEST DONE $(date)" >> ~/hrono-eval/full-score.log
